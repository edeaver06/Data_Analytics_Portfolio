# Google Fiber: the story in plain English

[Back to the project page](README.md) · [The code and how it's built](code/README.md)

**The setting:** Google Fiber sells home internet. When something goes wrong, customers call support. Ideally the problem is fixed on that first call. When it isn't, the customer calls back.

**The question:** which problems and which cities (called "markets" here) cause the most callbacks?

**The data:** a practice dataset from the Google Data Analytics certificate: 3 markets, 5 problem types, every day from Jan 1 to Mar 31, 2022. It counts first calls and any repeat calls in the 7 days after.

> **One term:** *repeat rate* = repeat calls ÷ first calls. A 30% repeat rate means that for every 100 first calls, 30 more calls came back within a week.

## 1. Which problems cause the most callbacks?

There were 64,939 first calls and 20,240 repeat calls (an overall repeat rate of 31.2%). Wi-Fi & Internet problems alone account for 50.7% of the repeat calls, and Technical Troubleshooting for another 29.6%.

![Repeat calls by problem type](code/figures/repeat_volume_by_category.png)

**What this means:** two problem types create 80.2% of the callbacks. Fixing first-call diagnosis for Wi-Fi and technical issues is the biggest lever.

## 2. Is it the same in every market?

Mostly. Wi-Fi + Technical make up 87.1% of repeats in market_1 and 89.3% in market_2, but only 66.5% in market_3.

![Share of repeats from Wi-Fi and technical problems, by market](images/wifi_tech_share_by_market.png)

**What this means:** the pattern holds everywhere. Market_3 looks different, which is a reason to look closer at market_3.

## 3. Which market has the most callbacks?

Market_3: 44.7% of its first calls lead to a repeat call, compared with 27.9% in market_1 and 17.9% in market_2.

![Repeat rate by market](images/repeat_rate_by_market.png)

**What this means:** market_3 is the outlier. Before blaming its support team, check its data.

## 4. Is Billing really a problem?

At first glance Billing has the worst repeat rate: 67.5%. But market_3 records 1,498 Billing repeat calls against only 759 Billing first calls. You can't have more follow-up calls than calls, so this is most likely a data or labelling error. Without market_3, Billing's repeat rate is 32.3%, in line with the other problem types.

![Billing repeat rate with and without market_3](images/billing_with_without_market3.png)

**What this means:** a striking number can be a data problem. Fix market_3's data before making any decision about Billing.

## 5. Which problems are hardest to fix in one call?

Looking at the rate rather than the volume: Billing 67.5% (see above), Scheduling 60.6%, Construction 34.1%, Wi-Fi & Internet 33.8%, Technical Troubleshooting 21.2%.

![Repeat rate by problem type](code/figures/repeat_rate_by_category.png)

**What this means:** Scheduling problems are small in volume (1,469 repeats) but usually need another call. Letting customers see their appointment status is a cheap idea to test.

## 6. Do callbacks change week to week?

Weekly repeat calls rise and fall with the number of first calls. The first week is partial because the data starts on Jan 1.

![Weekly first and repeat calls](code/figures/weekly_trend.png)

**What this means:** callbacks follow overall call volume. That's a pattern, not proof of what causes them.

## Summary
1. Wi-Fi & Internet and Technical Troubleshooting cause 80.2% of repeat calls.
2. Market_3 has the highest repeat rate (44.7%).
3. Market_3's Billing numbers are impossible and need fixing before anyone acts on them.
4. Scheduling is small but hard to resolve in one call (60.6%).

## Limitations (in plain words)
- **Practice data.** This is a fictional, anonymized dataset from a training course, not real Google Fiber records.
- **Only three months** (Q1 2022).
- **No reasons or costs.** The data doesn't say why customers called back or what each call cost, so the suggestions are ideas to test, not proven fixes.
- **Repeat rate is simplified.** One customer can call back more than once, which the data can't separate.
