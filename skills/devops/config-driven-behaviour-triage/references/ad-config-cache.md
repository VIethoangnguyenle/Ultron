# AD_CONFIG — cache, reload, và ví dụ đã kiểm (dvnh-common / vbsme)

## Cache (nguyên nhân số 1 của "đọc config thấy X mà hành vi không đổi")

- Config đọc qua `IConfigFactory.getConfigValue(id)` → `ConfigFactory` (extends `BaseCrudLocalCacheFactory`).
- `ConfigFactory` override `cacheFactory().singleTtl() = Duration.ofHours(1)` — trong khi default của
  `CacheConfigFactory.singleTtl()` chỉ **50 giây**. ⇒ Riêng AD_CONFIG giữ giá trị cũ tới **~1 giờ**.
- Cache là **local theo từng instance** (không phải cache chung) ⇒ sửa DB xong các instance có thể trả
  kết quả khác nhau trong cùng một khoảng thời gian.
- Reload chỉ xảy ra khi có event Kafka `ReloadCacheModel` với factory = `AD_CONFIG`
  (`ReloadCacheFactoryConstants.CONFIG_FACTORY`); subscriber theo service (`*ServiceReloadCacheSubscriber`).
  Sửa DB bằng SQL trực tiếp **không** sinh event này.
- `getConfigValue` ném lỗi khi không tìm thấy key (kèm log `Get Config Not Found for key: <id>`) ⇒ config thiếu
  KHÔNG im lặng bỏ qua kiểm tra, nó làm request lỗi ở chỗ khác. Đừng nhầm với "gate không chạy".
- Repository đọc row `findByIdAndActiveIsTrue` ⇒ row `IS_ACTIVE = 0` coi như không tồn tại.

## Ví dụ đã kiểm — tra cứu lịch sử giao dịch tài khoản (vbsme)

- Gate nằm ở `preHandle` của handler tra cứu (`GetAccountTransactionHistoriesHandler`, bank-service).
  So `TimeUtil.betweenDays(from.atStartOfDay(), to.atStartOfDay())` = `|ChronoUnit.DAYS.between|`
  ⇒ đơn vị là **NGÀY** (không phải tháng, không phải số bản ghi).
- So sánh **strict `>`**: `if (daysDiff > maxDuration)` → ném
  `TransactionError.EXCEED_MAX_DURATION_QUERY_FOR_TRANSACTIONS` (mã `500045`). Range đúng bằng ngưỡng lọt.
  Cùng handler còn gate page size (`EXCEED_MAX_PAGE_SIZE_QUERY_FOR_TRANSACTIONS`) so cùng kiểu.
- **3 key anh em** cho cùng khái niệm "thời gian tra cứu tối đa", dùng ở 3 nhánh khác nhau:

  | Key (AD_CONFIG) | Nhánh dùng |
  |---|---|
  | `financial.transaction.max_query_duration` | tra cứu lịch sử GD tài khoản (VBG) |
  | `financial.hbk.transaction.max_query_duration` | tra cứu giao dịch kênh HBK |
  | `financial.pos.transaction.max_query_duration` | tra cứu giao dịch kênh POS |

  Giá trị khác nhau giữa key và giữa env (SIT từng thấy 62 / 92 / 92 ở thời điểm kiểm) ⇒ **luôn query lại**
  trước khi kết luận, đừng nhớ số.
- Log khi gate nổ in **giá trị runtime**: `Exceed max duration %d days for account transactions. DaysDiff: %d`
  ⇒ dùng làm bằng chứng instance đang dùng giá trị nào.
