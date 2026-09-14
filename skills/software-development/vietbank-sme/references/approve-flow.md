# Luồng DUYỆT LỆNH (approve) — init + confirm, và finalStage

Nguồn: trace source thật 2026-09-12 (repo vietbank-sme-omni). Trả lời nhóm nghiệp vụ: docs/flows/duyet-lenh-init-confirm-flow.md. Bản mô hình hoá riêng bước confirm ("init xong thì xác nhận gọi vào đâu"): docs/flows/duyet-lenh-confirm-sau-init-flow.md.

## Endpoints (client)
- Init duyệt: `POST /api/v1/{web|app}/trans-reqs/approve/init` (+ batch: /trans-reqs/batch-approve/init)
- Confirm tài chính: `POST /api/v1/{web|app}/transfer/confirm` (batch: /transfer/batch-confirm)
- Confirm phi tài chính: `POST /api/v1/{web|app}/auth/nonfinancial/confirm`
- Từ chối: /trans-reqs/reject/init; huỷ: /trans-reqs/cancel/init

## Init (approval-service)
`BaseInitTransReqActionHandler` → chain `TransReqActionSelectorChain`:
1. Check customer profile status (EXPIRED → lỗi), check app version + device risk per service.
2. Bắt buộc note (Khách hàng chưa nhập nội dung duyệt → lỗi).
3. Tài chính: `getActiveWorkflowStage` = **next stage** của stage hiện tại của lệnh; user phải có quyền trong workflow stage của mình; next stage phải có auth methods → `filterFinancialAuthMethods(..., approvedStage.isFinalized())`.
4. Phi tài chính: chỉ `legalRepresentative` (người đại diện pháp luật) được duyệt; stage từ bảng phi tài chính.
5. **`request.setFinalStage(approvingStage.isFinalized())`** — field `finalStage` nằm trong `BaseTransReqActionRequest` với `@JsonIgnore` ⇒ client KHÔNG truyền, server tự set.
6. Chain processor theo action:
   - Tài chính + `finalStage` → gRPC `InitFinalApproveFinancialTransaction` (transaction-service: validate hạn mức/số dư/loại RLE/phí — ValidateTransactionLimit/SenderPaymentAccount/BranchFeeAccount/RleCustomerType/TransactionAmount → phase `INIT_FINAL_APPROVED_TRANSACTION` "Khởi tạo luồng Duyệt lệnh cuối").
   - Tài chính + !finalStage → `InitApproveFinancialTransaction` (phase `INIT_APPROVED_TRANSACTION` "Khởi tạo luồng Xác nhận").
   - Tương tự cặp Init/FinalApprove cho phi tài chính.
   - Lỗi trạng thái lệnh → `syncActiveTransReq` (đồng bộ lại lệnh doanh nghiệp) rồi mới throw.
7. Response: transToken + authMethods + thông tin lệnh; hiệu lực theo `CONFIRM_TRANSACTION_DURATION` (AD_CONFIG).

## Confirm — "init xong thì xác nhận gọi vào đâu"
**Endpoint không nằm ở approval-service, và logic cũng không nằm trong service nghiệp vụ:** controller của service nghiệp vụ nhận request (tài chính: transfer-service `/transfer/confirm`, batch `/transfer/batch-confirm`; phi tài chính: auth-service `/auth/nonfinancial/confirm`) nhưng **handler + executor confirm nằm ở module dùng chung `transaction/business`** (`BaseConfirmTransactionHandler` → `BaseTransactionConfirmExecutor` + `*ConfirmExecutorManager`). Grep confirm trong từng service riêng sẽ không thấy logic ⇒ nhớ điểm này khi trả lời "gọi vào đâu" hoặc khi định vị bug.

`BaseConfirmTransactionHandler.preHandle` (chạy TRƯỚC executor):
1. Lock phân tán `TRANSACTION_CONFIRM_<transToken>` (`ExpirableLockRegistry`) — không lấy được lock (double submit / 2 thiết bị cùng bấm) → `INVALID_REQUEST` ngay.
2. `buildConfirmRequest` → `getWaitConfirmTransaction(sessionId, customerId, transToken)`; hết hạn/không có → lỗi, phải init lại.
3. `getConfirmType(phase)` đầy đủ: INIT_REQUEST | ACCEPT_SUSPICIOUS_TRANSACTION → `CONFIRM_TRANS_REQ`; INIT_REJECTED → `CONFIRM_REJECTED`; INIT_APPROVED → `CONFIRM_APPROVED`; INIT_UNAPPROVED → `CONFIRM_UNAPPROVED`; INIT_CANCEL → `CONFIRM_CANCEL`; còn lại (INIT_FINAL_APPROVED) → **default ⇒ `CONFIRM_FINAL_APPROVED`**.
4. `decorateTransaction`: chỉ final-approved / rejected mới ghi `lastApproved*`; chỉ CONFIRM_TRANS_REQ / CONFIRM_UNAPPROVED mới sinh `traceNo`.
5. Verify auth method (OTP/SoftOTP/password) → **evict cache wait-confirm** với key `sessionId` + `customerId` (KHÔNG có transToken) ⇒ mã chỉ dùng được 1 lần.

`BaseTransactionConfirmExecutor.onConfirmed` rẽ theo `confirmType` (tạo lệnh / không phê duyệt / từ chối / huỷ), mặc định → `onConfirmTransReq`:
6. Chọn executor theo `serviceCode` (`getExecutor`) — không có executor → `UNSUPPORTED`.
7. `onCallApprovalServiceConfirmTransReq` → **gRPC `IApprovalClient.confirmTransReq`** (hàng loạt: `confirmTransReqs` qua `BaseTransactionsBatchConfirmExecutor`) gửi transReqId + transToken + auth methods + customer/session.
8. Approval side (`ConfirmTransReqHandler`): load lại active req theo transToken trong cache wait-confirm → `isFinalApprovingStage()` ? `completeActiveTransReq` (đóng lệnh, trả transactionId) : `update` → stage kế tiếp; `postHandle` evict cache wait-confirm + cache overview lệnh của người thực hiện.
9. Chỉ `CONFIRM_FINAL_APPROVED` (và nhánh không phê duyệt) mới gọi `onConfirmedTransaction` → **hạch toán core**, response `finalApproved=true`. Duyệt cấp giữa **KHÔNG** hạch toán — lệnh vẫn ở trạng thái đang duyệt, cấp sau phải init + confirm lại.
10. Fail → `onConfirmedFailure`: lỗi thuộc `CONFIRM_APPROVAL_SERVICE_FAILED_ERRORS` → phase **`WAITING_REAPPROVAL`** ("chờ duyệt lại", KHÔNG phải thất bại hẳn); còn lại → status theo loại lỗi (FAILED / TIMEOUT / PENDING).

## finalStage true khi nào
- = stage duyệt kế tiếp có `IS_FINALIZED = 1`.
- Tài chính: `OMNI_WORKFLOW_STAGE` (NEXT_STAGE_ID, LEVEL, IS_INITIALIZED, IS_FINALIZED) + `OMNI_WORKFLOW_STAGE_CUSTOMER` (ai duyệt cấp nào).
- Phi tài chính: `OMNI_NONFINANCIAL_WORKFLOW_STAGE` (NEXT_STAGE_ID, IS_INITIALIZED, IS_FINALIZED, METHODS).
- `isFinalApprovingStage()`: status REJECTED/CANCELED → true (đóng lệnh, không hạch toán); không có approvingStage → false.
- Lệnh đã tạo giữ stage theo cấu hình tại thời điểm tạo ⇒ BO đổi cấu hình cấp cuối sau đó thì phải tạo lệnh MỚI.

## Bảng DB
`OMNI_TRANSACTION`, `OMNI_ACTIVE_TRANS_REQ`, `OMNI_ACTIVE_TRANS_REQ_STAGE`, `OMNI_COMPLETED_TRANS_REQ_STAGE`,
`OMNI_WORKFLOW_STAGE`, `OMNI_NONFINANCIAL_WORKFLOW_STAGE`, `OMNI_WORKFLOW_STAGE_CUSTOMER`, `AD_WORKFLOW_STAGE_SCHEME`.
`TransReqStatus`: 0=REJECTED, 1=APPROVED, 2=FAILED, 3=PENDING_APPROVED, 4=CANCELED, 5=PENDING_RESULT.
