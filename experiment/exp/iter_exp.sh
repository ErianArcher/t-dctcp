#!/bin/bash

folder_path="./iter_result"
if [ ! -d "$folder_path" ]; then
    /bin/mkdir "$folder_path"
fi

for i in {1..30}
do
    fname="$folder_path/result$i"
    sudo ./run-exp.sh
    /bin/mkdir "$fname"
    sudo mv fct_* comparison/CDF_RTT.png dctcp-n16-bw100 tdctcp-n16-bw100 "$fname"
done