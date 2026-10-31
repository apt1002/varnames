#!/bin/bash
# The break-open prior vs the independence prior P_mar, on held-out data.
# Run sequentially — the trace passes are memory hungry.
#
#   scripts/run_break_open_prior.sh
#
# Outputs work/tw*_breakopen*.log and the saved traces work/tw*_trace*.npy (a
# trace holds the per-level merge events, so the prior can be rebuilt for a new
# alpha in ~10 s via --load-trace).
set -e
cd "$(dirname "$0")/.."
P=scripts/break_open_prior.py

# the three standard sizes: dictionary + counts from the tw* training sample
python3 $P --dir work/tw96   --score-stride 20 --kappas 10,30,100,300,1000,3000 \
  --modes mar,break,breakz --save-trace work/tw96_trace.npy  > work/tw96_breakopen.log 2>&1
python3 $P --dir work/tw512  --score-stride 20 --kappas 10,30,100,300,1000,3000 \
  --modes mar,break,breakz --save-trace work/tw512_trace.npy > work/tw512_breakopen.log 2>&1
python3 $P --dir work/tw2040 --score-stride 20 --kappas 10,30,100,300,1000,3000 \
  --modes mar,break,breakz --save-trace work/tw2040_trace.npy > work/tw2040_breakopen.log 2>&1

# data-size sensitivity at tw2040 (a fresh dictionary at each stride, so both
# priors see the same model)
python3 $P --dir work/tw2040 --train-stride 40 --score-stride 40 \
  --kappas 10,30,100,300,1000 --modes mar,break \
  --save-trace work/tw2040_trace_s40.npy > work/tw2040_breakopen_s40.log 2>&1
python3 $P --dir work/tw2040 --train-stride 10 --score-stride 40 \
  --kappas 10,30,100,300,1000 --modes mar,break \
  --save-trace work/tw2040_trace_s10.npy > work/tw2040_breakopen_s10.log 2>&1

# the lambda-mixture test (does the break shape add anything to P_mar?)
python3 $P --dir work/tw2040 --load-trace work/tw2040_trace.npy --score-stride 20 \
  --mix --kappas 10,30,100,300,1000 > work/tw2040_breakopen_mix.log 2>&1
echo "wrote work/tw*_breakopen*.log"
