#include <linux/module.h>
#include <linux/mm.h>
#include <net/tcp.h>
#include <linux/inet_diag.h>

#define TDCTCP_MAX_ALPHA	1024U
#define TDCTCP_MAX_RTT 0xffffffffU

struct tdctcp {
	u8 doing_tdctcp_now; /* if true, do tdctcp for this rtt */
	u32 acked_bytes_ecn;
	u32 acked_bytes_total;
	u32 prior_snd_una;
	u32 prior_rcv_nxt;
	u32 tdctcp_alpha;
	/* part for rtt measurement */
    u32 base_rtt; 
    u32 min_rtt;
    u32 prev_rtt;
    u32 diff;
    u8 complete_event;
    u32 cwnd;
	// END
	u32 next_seq;
	u32 ce_state;
	u32 delayed_ack_reserved;
	u32 loss_cwnd;
};

static unsigned int tdctcp_shift_g __read_mostly = 4; /* g = 1/2^4 */
module_param(tdctcp_shift_g, uint, 0644);
MODULE_PARM_DESC(tdctcp_shift_g, "parameter g for updating tdctcp_alpha");

static unsigned int tdctcp_alpha_on_init __read_mostly = TDCTCP_MAX_ALPHA;
module_param(tdctcp_alpha_on_init, uint, 0644);
MODULE_PARM_DESC(tdctcp_alpha_on_init, "parameter for initial alpha value");

static unsigned int tdctcp_clamp_alpha_on_loss __read_mostly;
module_param(tdctcp_clamp_alpha_on_loss, uint, 0644);
MODULE_PARM_DESC(tdctcp_clamp_alpha_on_loss,
		 "parameter for clamping alpha on loss");

static unsigned int tdctcp_alpha_factor __read_mostly = TDCTCP_MAX_ALPHA >> 3;
module_param(tdctcp_alpha_factor, uint, 0644);
MODULE_PARM_DESC(tdctcp_alpha_factor,
         "A factor appeals if the network is in the state of mid or high congestion");

/* EWMA weight parameter for rtt_diff */
static unsigned int tdctcp_shift_beta __read_mostly = 3; /* beta = 1/2^3*/
module_param(tdctcp_shift_beta, uint, 0644);
MODULE_PARM_DESC(tdctcp_shift_beta, "parameter beta for updating rtt_diff");

/* additive increment factor */
static unsigned int tdctcp_addstep __read_mostly = 1;
module_param(tdctcp_addstep, uint, 0644);
MODULE_PARM_DESC(tdctcp_addstep, "parameter addstep for increasing cwnd");

/* multiplicative decrement factor */
static unsigned int tdctcp_multi __read_mostly = 2; /* multi = 0.25*/
module_param(tdctcp_multi, uint, 0644);
MODULE_PARM_DESC(tdctcp_multi, "parameter mutil for multiplicatively decreasing cwnd");

static unsigned int tdctcp_decre __read_mostly = 1;
module_param(tdctcp_decre, uint, 0644);
MODULE_PARM_DESC(tdctcp_decre, "parameter for mid or high congestion");

/* limit on increase 
 * (this paramter should be changed according to bandwidth)
 * 50000us for 100Mbps
 * 5000us for 1Gbps
 * 500us for 10Gbps
 */
static unsigned int tdctcp_thigh __read_mostly = 50000;
module_param(tdctcp_thigh, uint, 0644);
MODULE_PARM_DESC(tdctcp_thigh, "parameter thigh for limit on increase");

/* filter on RTT spikes
 * (this paramter should be changed according to bandwidth)
 * 5000us for 100Mbps
 * 500us for 1Gbps
 * 50us for 10Gbps
 */
static unsigned int tdctcp_tlow __read_mostly = 5000;
module_param(tdctcp_tlow, uint, 0644);
MODULE_PARM_DESC(tdctcp_tlow, "parameter tlow as a filter on RTT spikes");


static struct tcp_congestion_ops tdctcp_reno;

static void tdctcp_reset(const struct tcp_sock *tp, struct tdctcp *ca)
{
	ca->next_seq = tp->snd_nxt;

	ca->acked_bytes_ecn = 0;
	ca->acked_bytes_total = 0;
}

static void tdctcp_enable(struct sock *sk)
{
    struct tdctcp *ca = inet_csk_ca(sk);

    ca->doing_tdctcp_now = 1;
    ca->min_rtt = TDCTCP_MAX_RTT;
    ca->prev_rtt = TDCTCP_MAX_RTT;
    ca->diff = 0U;
    ca->complete_event = 0U;
}

static void tdctcp_disable(struct sock *sk)
{
    struct tdctcp *ca = inet_csk_ca(sk);

    ca->doing_tdctcp_now = 0;
}

static void tdctcp_init(struct sock *sk)
{
	const struct tcp_sock *tp = tcp_sk(sk);

	if ((tp->ecn_flags & TCP_ECN_OK) ||
	    (sk->sk_state == TCP_LISTEN ||
	     sk->sk_state == TCP_CLOSE)) {
		struct tdctcp *ca = inet_csk_ca(sk);

		ca->prior_snd_una = tp->snd_una;
		ca->prior_rcv_nxt = tp->rcv_nxt;

		tdctcp_enable(sk);

		ca->tdctcp_alpha = min(tdctcp_alpha_on_init, TDCTCP_MAX_ALPHA);

		ca->base_rtt = TDCTCP_MAX_RTT;
        ca->cwnd = 2U;

		ca->delayed_ack_reserved = 0;
		ca->loss_cwnd = 0;
		ca->ce_state = 0;

		tdctcp_reset(tp, ca);
		return;
	}

	/* No ECN support? Fall back to Reno. Also need to clear
	 * ECT from sk since it is set during 3WHS for tdctcp.
	 */
	inet_csk(sk)->icsk_ca_ops = &tdctcp_reno;
	tdctcp_disable(sk);
	INET_ECN_dontxmit(sk);
}

/**
 * Author: Liang Junpeng
 * This function is for avoiding overflow
 **/
static u32 mul_ratio(u32 tar, u32 numerator, u32 denominator)
{
	u32 ret = tar;
	u32 mul = 0U;
	if (numerator < denominator)
		ret = tar * numerator / denominator;
	else
	{
		mul = numerator / denominator;
		numerator -= mul * denominator;
		if (TDCTCP_MAX_RTT / max(1U, numerator) >= ret)
			ret = ret * numerator / denominator + ret * mul;
		else // In case that ret * numerator overflows
			ret = ret / denominator * numerator + ret * mul;
	}
	return ret;
}

/*
 * Author: Liang Junpeng
 * This function is for calculating new cwnd (Main Algorithm)
 * return: new cwnd value
 */
static u32 update_cwnd(struct sock *sk)
{
    struct tdctcp *ca = inet_csk_ca(sk);
    const struct tcp_sock *tp = tcp_sk(sk);
    u32 x;
    u32 cnt_cwnd = tp->snd_cwnd;
    u32 normalized_gradient = ca->diff; /* normalized_gradient = diff / min_rtt*/

    if (ca->tdctcp_alpha < tdctcp_alpha_factor)
    {
        if (ca->prev_rtt < tdctcp_tlow)
        {
            ca->complete_event = 0U;
            return cnt_cwnd + tdctcp_addstep;
        }
        if (ca->prev_rtt > tdctcp_thigh)
        {
            ca->complete_event = 0U;
			x = ca->prev_rtt - tdctcp_thigh;
			return mul_ratio(cnt_cwnd >> tdctcp_multi, x, max(1U, ca->prev_rtt)) -
			((cnt_cwnd * ca->tdctcp_alpha) >> 11U);
        }
        if (normalized_gradient <= 0)
        {
            cnt_cwnd += tdctcp_addstep;
            if (ca->complete_event >= 5U)
            {
                cnt_cwnd += 4*tdctcp_addstep;
                ca->complete_event = 0U;
            }
            ca->complete_event++;
        }
        else
        {
            ca->complete_event = 0U;
			x = mul_ratio((cnt_cwnd >> tdctcp_multi), normalized_gradient, max(1U,ca->min_rtt)); // temp value
			cnt_cwnd = min(x, cnt_cwnd - ((cnt_cwnd * ca->tdctcp_alpha) >> 11U));
        }
    }
    else if (ca->tdctcp_alpha <= TDCTCP_MAX_ALPHA)
    {
        ca->complete_event = 0U;
        if (ca->prev_rtt < tdctcp_tlow)
        {
            return cnt_cwnd - ((cnt_cwnd * ca->tdctcp_alpha) >> (11U + tdctcp_decre));
        }
        if (ca->prev_rtt > tdctcp_thigh)
        {
            return cnt_cwnd >> 1;
        }
		// Other situation
		if (normalized_gradient <= 0)
			cnt_cwnd -= (cnt_cwnd * ca->tdctcp_alpha) >> (11U + tdctcp_decre);
        else
			cnt_cwnd -= (cnt_cwnd * ca->tdctcp_alpha) >> 11U;
    }

    return cnt_cwnd;
}


static u32 tdctcp_ssthresh(struct sock *sk)
{
	struct tdctcp *ca = inet_csk_ca(sk);
	struct tcp_sock *tp = tcp_sk(sk);

	ca->loss_cwnd = tp->snd_cwnd;
	return max(ca->cwnd, 2U); // When slow start is trigued, this function will be called
}

/**
 * Author: Liang Junpeng
 * Compute rtt difference and record new rtt each time when ack arrives
 **/
static void tdctcp_pkts_acked(struct sock *sk, const struct ack_sample *sample)
{
    struct tdctcp *ca = inet_csk_ca(sk);
    struct tcp_sock *tp = tcp_sk(sk);
    u32 vrtt;
    u32 vdiff;
	u32 diff = ca->diff;

	// printk(KERN_DEBUG "%d    ", rtt_us);
    if(sample->rtt_us < 0)
        return;
    
    /* Never allow zero rtt or base_rtt */
    vrtt = sample->rtt_us + 1;

    if (vrtt < ca->base_rtt)
        ca->base_rtt = vrtt;
    
    ca->min_rtt = min(ca->min_rtt, vrtt);
    
    vdiff = vrtt - ca->prev_rtt;
    ca->prev_rtt = vrtt;
    
    diff -= diff >> tdctcp_shift_beta;
    diff += vdiff >> tdctcp_shift_beta;

	ca->diff = diff;
    ca->cwnd = update_cwnd(sk);
    // If new cwnd is greater than current cwnd then update it
    tp->snd_cwnd = max(tp->snd_cwnd, ca->cwnd);
}

/* Minimal DCTP CE state machine:
 *
 * S:	0 <- last pkt was non-CE
 *	1 <- last pkt was CE
 */

static void tdctcp_ce_state_0_to_1(struct sock *sk)
{
	struct tdctcp *ca = inet_csk_ca(sk);
	struct tcp_sock *tp = tcp_sk(sk);

	/* State has changed from CE=0 to CE=1 and delayed
	 * ACK has not sent yet.
	 */
	if (!ca->ce_state && ca->delayed_ack_reserved) {
		u32 tmp_rcv_nxt;

		/* Save current rcv_nxt. */
		tmp_rcv_nxt = tp->rcv_nxt;

		/* Generate previous ack with CE=0. */
		tp->ecn_flags &= ~TCP_ECN_DEMAND_CWR;
		tp->rcv_nxt = ca->prior_rcv_nxt;

		tcp_send_ack(sk);

		/* Recover current rcv_nxt. */
		tp->rcv_nxt = tmp_rcv_nxt;
	}

	ca->prior_rcv_nxt = tp->rcv_nxt;
	ca->ce_state = 1;

	tp->ecn_flags |= TCP_ECN_DEMAND_CWR;
}

static void tdctcp_ce_state_1_to_0(struct sock *sk)
{
	struct tdctcp *ca = inet_csk_ca(sk);
	struct tcp_sock *tp = tcp_sk(sk);

	/* State has changed from CE=1 to CE=0 and delayed
	 * ACK has not sent yet.
	 */
	if (ca->ce_state && ca->delayed_ack_reserved) {
		u32 tmp_rcv_nxt;

		/* Save current rcv_nxt. */
		tmp_rcv_nxt = tp->rcv_nxt;

		/* Generate previous ack with CE=1. */
		tp->ecn_flags |= TCP_ECN_DEMAND_CWR;
		tp->rcv_nxt = ca->prior_rcv_nxt;

		tcp_send_ack(sk);

		/* Recover current rcv_nxt. */
		tp->rcv_nxt = tmp_rcv_nxt;
	}

	ca->prior_rcv_nxt = tp->rcv_nxt;
	ca->ce_state = 0;

	tp->ecn_flags &= ~TCP_ECN_DEMAND_CWR;
}

static void tdctcp_update_alpha(struct sock *sk, u32 flags)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	struct tdctcp *ca = inet_csk_ca(sk);
	u32 acked_bytes = tp->snd_una - ca->prior_snd_una;

	/* If ack did not advance snd_una, count dupack as MSS size.
	 * If ack did update window, do not count it at all.
	 */
	if (acked_bytes == 0 && !(flags & CA_ACK_WIN_UPDATE))
		acked_bytes = inet_csk(sk)->icsk_ack.rcv_mss;
	if (acked_bytes) {
		ca->acked_bytes_total += acked_bytes;
		ca->prior_snd_una = tp->snd_una;

		if (flags & CA_ACK_ECE)
			ca->acked_bytes_ecn += acked_bytes;
	}

	/* Expired RTT */
	if (!before(tp->snd_una, ca->next_seq)) {
		u64 bytes_ecn = ca->acked_bytes_ecn;
		u32 alpha = ca->tdctcp_alpha;

		/* alpha = (1 - g) * alpha + g * F */

		alpha -= min_not_zero(alpha, alpha >> tdctcp_shift_g);
		if (bytes_ecn) {
			/* If tdctcp_shift_g == 1, a 32bit value would overflow
			 * after 8 Mbytes.
			 */
			bytes_ecn <<= (10 - tdctcp_shift_g);
			do_div(bytes_ecn, max(1U, ca->acked_bytes_total));

			alpha = min(alpha + (u32)bytes_ecn, TDCTCP_MAX_ALPHA);
		}
		/* tdctcp_alpha can be read from tdctcp_get_info() without
		 * synchro, so we ask compiler to not use tdctcp_alpha
		 * as a temporary variable in prior operations.
		 */
		WRITE_ONCE(ca->tdctcp_alpha, alpha);
		tdctcp_reset(tp, ca);
	}
}

static void tdctcp_state(struct sock *sk, u8 new_state)
{
	if (tdctcp_clamp_alpha_on_loss && new_state == TCP_CA_Loss) {
		struct tdctcp *ca = inet_csk_ca(sk);

		/* If this extension is enabled, we clamp tdctcp_alpha to
		 * max on packet loss; the motivation is that tdctcp_alpha
		 * is an indicator to the extend of congestion and packet
		 * loss is an indicator of extreme congestion; setting
		 * this in practice turned out to be beneficial, and
		 * effectively assumes total congestion which reduces the
		 * window by half.
		 */
		ca->tdctcp_alpha = TDCTCP_MAX_ALPHA;
	}
}

static void tdctcp_update_ack_reserved(struct sock *sk, enum tcp_ca_event ev)
{
	struct tdctcp *ca = inet_csk_ca(sk);

	switch (ev) {
	case CA_EVENT_DELAYED_ACK:
		if (!ca->delayed_ack_reserved)
			ca->delayed_ack_reserved = 1;
		break;
	case CA_EVENT_NON_DELAYED_ACK:
		if (ca->delayed_ack_reserved)
			ca->delayed_ack_reserved = 0;
		break;
	default:
		/* Don't care for the rest. */
		break;
	}
}

static void tdctcp_cwnd_event(struct sock *sk, enum tcp_ca_event ev)
{
	switch (ev) {
	case CA_EVENT_ECN_IS_CE:
		tdctcp_ce_state_0_to_1(sk);
		break;
	case CA_EVENT_ECN_NO_CE:
		tdctcp_ce_state_1_to_0(sk);
		break;
	case CA_EVENT_DELAYED_ACK:
	case CA_EVENT_NON_DELAYED_ACK:
		tdctcp_update_ack_reserved(sk, ev);
		break;
	default:
		/* Don't care for the rest. */
		break;
	}
}

static u32 tdctcp_cwnd_undo(struct sock *sk)
{
	const struct tdctcp *ca = inet_csk_ca(sk);

	return max(tcp_sk(sk)->snd_cwnd, ca->loss_cwnd);
}

static struct tcp_congestion_ops tdctcp __read_mostly = {
	.init		= tdctcp_init,
	.in_ack_event   = tdctcp_update_alpha,
	.cwnd_event	= tdctcp_cwnd_event,
	.ssthresh	= tdctcp_ssthresh,
	.pkts_acked = tdctcp_pkts_acked, // New function
	.cong_avoid	= tcp_reno_cong_avoid,
	.undo_cwnd	= tdctcp_cwnd_undo,
	.set_state	= tdctcp_state,
	.flags		= TCP_CONG_NEEDS_ECN,
	.owner		= THIS_MODULE,
	.name		= "tdctcp",
};

static struct tcp_congestion_ops tdctcp_reno __read_mostly = {
	.ssthresh	= tcp_reno_ssthresh,
	.cong_avoid	= tcp_reno_cong_avoid,
	.undo_cwnd	= tcp_reno_undo_cwnd,
	.owner		= THIS_MODULE,
	.name		= "tdctcp-reno",
};

static int __init tdctcp_register(void)
{
	BUILD_BUG_ON(sizeof(struct tdctcp) > ICSK_CA_PRIV_SIZE);
	return tcp_register_congestion_control(&tdctcp);
}

static void __exit tdctcp_unregister(void)
{
	tcp_unregister_congestion_control(&tdctcp);
}

module_init(tdctcp_register);
module_exit(tdctcp_unregister);


MODULE_AUTHOR("Erian Liang <jungg1996@gmail.com>");
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("TIMELY & DataCenter TCP (T-DCTCP)");
