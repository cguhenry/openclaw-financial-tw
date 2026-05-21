# MOPS Major Announcements Source

Date: 2026-05-19

## Official Source

- Primary page: https://mopsov.twse.com.tw/mops/web/t05sr01_1
- Same-page Ajax endpoint: https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1
- Detail page pattern: https://mopsov.twse.com.tw/mops/web/t05sr01_1?encodeURIComponent=1&TYPEK=<typek>&step=1&firstin=true&COMPANY_ID=<stock_id>&SPOKE_DATE=<yyyymmdd>&SPOKE_TIME=<hhmmss>&SEQ_NO=<seq_no>
- Fallback feed: https://www.twse.com.tw/res/data/zh/home/news.json

## Market Filter

The MOPS page uses TYPEK to select market:

- all: 全體公司
- sii: 上市公司
- otc: 上櫃公司
- rotc: 興櫃公司
- pub: 公開發行公司

## Implemented MCP Tool

get_major_announcements(stock_id=None, market="all", limit=20, summary_count=5, include_details=False)

Returned rows include:

- company_id
- company_name
- market
- market_label
- spoke_date_roc
- spoke_date
- spoke_date_iso
- spoke_time
- spoke_time_local
- seq_no
- skey
- title
- category
- detail_url

When include_details=True, each returned row also includes:

- speaker
- speaker_title
- speaker_phone
- subject
- clause
- fact_date_roc
- fact_date_iso
- description
- raw_fields
