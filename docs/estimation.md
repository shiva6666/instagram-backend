# Capacity estimation

Use the following baseline for an initial Instagram-like workload estimate.

## Assumptions

- Total registered users: 100M
- Daily active percentage: 20%
- Daily active users: 20M
- Posts per active user per day: 0.2
- Average followers per user: 200
- Feed reads per active user per day: 10
- Writes per active user per day: 1
- Average media payload per post: 500 KB
- Peak-to-average traffic ratio: 5x
- Timeline entries retained per user in Redis: 500
- Redis bytes per timeline entry, including overhead: 64 bytes

## Estimates

| Metric | Estimate | Calculation / formula |
|---|---:|---|
| Daily active users | 20M | `total users x daily active percentage` = `100M x 20%` |
| Posts per day | 4M | `DAU x posts/user/day` = `20M x 0.2` |
| Feed reads per day | 200M | `DAU x feed reads/user/day` = `20M x 10` |
| Writes per day | 20M | `DAU x writes/user/day` = `20M x 1` |
| Read/write ratio | 10:1 | `feed reads/day / writes/day` = `200M / 20M` |
| Feed reads QPS, average / peak | 2.3K / 11.5K | `daily reads / 86,400`; peak = `average x 5` |
| Writes QPS, average / peak | 230 / 1.2K | `daily writes / 86,400`; peak = `average x 5` |
| Media storage per day | 2 TB | `posts/day x average media payload/post` = `4M x 500 KB` |
| Media storage per year | 730 TB | `media/day x 365` = `2 TB x 365` |
| Redis timeline memory, active users | 640 GB raw | `DAU x entries/user x bytes/entry` = `20M x 500 x 64` |
| Redis timeline memory, all users | 3.2 TB raw | `registered users x entries/user x bytes/entry` = `100M x 500 x 64` |
| Redis timeline memory, planned | Raw memory plus overhead | Add sorted-set/list overhead, replication, and fragmentation |

## General formulas

```text
DAU = total registered users x daily active percentage
posts/day = DAU x posts per active user per day
reads/day = DAU x reads per active user per day
writes/day = DAU x writes per active user per day
average QPS = daily operations / 86,400
peak QPS = average QPS x peak-to-average ratio
read/write ratio = reads/day : writes/day
storage/year = posts/day x average media payload/post x 365
Redis timeline memory = users with timelines x entries/user x bytes/entry
```

Storage estimates should additionally multiply by the replication factor and
include thumbnails, multiple media per post, indexes, backups, and other
operational overhead. Define retention windows for notifications, outbox
events, idempotency keys, and expired refresh tokens before sizing long-term
storage.
