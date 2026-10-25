# Electricity prices: the story in plain English

[Back to the project page](README.md) · [The code](code/README.md)

**The question:** people keep saying AI data centers are pushing up power bills. Before testing that, I wanted the basic facts: how much have home electricity prices actually risen, and in which states?

**The data:** the US Energy Information Administration (EIA) publishes monthly average prices for every state, back to 2001. I pulled all of it through their free API: 46,971 rows.

> **One term:** *c/kWh* = cents per kilowatt-hour, the unit on your bill. Annual prices here are weighted by how much power was sold, so a big winter month counts more than a mild one.

## 1. Prices went up everywhere
The US residential average went from 8.58 c/kWh in 2001 to 18.02 over the latest 12 months, up 110%. General inflation rose about 85% over the same time, so the real increase is about 13%.

## 2. Where you live matters a lot
Hawaii pays 43.51 c/kWh; North Dakota pays 12.32. The dashboard lets you pick any state and see its trend, its change since 2001 (with and without inflation), and where it ranks.

## 3. Checking odd numbers instead of hiding them
- Maryland jumped 79% in March 2026, then fell back in April. I checked it against the live EIA API: that is what EIA reports, so it stays in, with a note.
- Colorado and New Mexico are missing some 2026 months, and Alaska's 2016 figures were not reported. They are flagged, not filled in.
- 19 states sit in more than one grid region, so the region summary is a rough grouping.

## 4. What about data centers?
Comparing states, more estimated data-center load went with *lower* current prices, and there was no clear link to recent increases. That is an association across states, not proof either way.
