# Luồng DUYỆT LỆNH (approve) — init + confirm, và finalStage

Nguồn: trace source thật 2026-09-12 (repo vietbank-sme-omni). Trả lời nhóm nghiệp vụ: docs/flows/duyet-lenh-init-confirm-flow.md.

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

## Confirm (transaction-service)
`BaseTransactionConfirmExecutor`:
1. Lock theo transToken (`CandidateLockingExecutor`) — double submit → lỗi confirm trùng.
2. `getWaitConfirmTransaction(transToken)` — hết hạn/không có → lỗi.
3. `getConfirmType(phase)`: INIT_APPROVED_TRANSACTION → CONFIRM_APPROVED_TRANSACTION; INIT_FINAL_APPROVED_TRANSACTION → **default ⇒ CONFIRM_FINAL_APPROVED_TRANSACTION** (các loại khác: INIT/REJECT/CANCEL...).
4. Verify auth method (OTP/SoftOTP/password) → `evictWaitConfirmTransaction` (xoá cache, không confirm lại).
5. Executor theo service code → `onConfirmedTransaction` (gRPC `IApprovalClient.confirmTransReq`) → approval side: nếu `activeTransReqModel.isFinalApprovingStage()` → `completeActiveTransReq` (đóng lệnh, trả transactionId) else chuyển sang stage kế tiếp.
6. Duyệt cuối → thực thi hạch toán (core) → status SUCCESS/FAILED/PENDING_RESULT; ghi lastApproved*; phi tài chính áp dụng thay đổi qua event.
7. Fail → `onConfirmedFailure` → đánh dấu thất bại + bắn topic.

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
