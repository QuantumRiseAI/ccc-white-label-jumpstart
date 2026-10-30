# Unity Biomedicines deployment cost model

`python3 cost_model.py` prints monthly and annual run cost for the five deployment options
on the "Deployment Options: Cost and What You Get" slide, under Low, Base and High usage.

Every option uses the same usage profile: 6 users, 3 analyses per close day, 2 follow-ups each.
Token shape per analysis: 120K input and 8K output on the first turn, then per follow-up 10K new
input, 3K output and a cached reread of the 120K prefix. API prices are Claude Sonnet 5.5 ($2/$10
per million, cache reads $0.20) and Opus 5.5 ($4/$20) for the High case.

Seat, infrastructure and ops-hour figures are list-price assumptions to confirm against Unity and
Plurality contracts. They live in `ASSUMPTIONS` and `OPTIONS` at the top of the script.
One-time build cost is excluded.
