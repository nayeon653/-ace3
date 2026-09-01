# Gold Answer 사람 검수 체크리스트

한투와 미래에셋 Gold Answer를 사람이 검수하기 위한 작업지입니다.
원본 표 대신 readable 검수본에서 해당 ID를 검색한 뒤, 아래 체크박스에 판정과 메모를 남기면 됩니다.

## 진행 규칙

- 아래 순서대로 검수합니다.
- `미지원`, `부분 지원`, `최신성 공백` 문항을 먼저 보고, `직접 지원`은 샘플만 확인합니다.
- 판정은 `OK`, `수정 필요`, `보류` 중 하나만 체크합니다.
- 수정이 필요하면 `수정 메모`에 바꿔야 할 문구나 근거 문제를 짧게 적습니다.

## 전체 요약

- 1차: 한투 미지원 6개 + 최신성 공백 1개: 7개
- 2차: 한투 부분 지원 14개: 14개
- 3차: 미래에셋 미지원 21개: 21개
- 4차: 미래에셋 부분 지원 36개: 36개
- 5차: 직접 지원 샘플 확인: 13개
- 총 검수 항목: 91개

## 1차: 한투 미지원 6개 + 최신성 공백 1개 (7개)

### 1. 한투 PROD-002 · 미지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-002` 검색
- 질문: 연금저축펀드 계좌에서는 위험자산 편입 비율에 제한이 있나요?

**목표 답변**

> 제공된 문서 집합만으로는 연금저축펀드 계좌의 위험자산 총량 제한 유무를 직접 확인할 수 없습니다. 매우 높은 위험(1등급) 상품에 연금저축계좌로 매입 가능한 클래스가 있다는 점은 확인되지만, 이것만으로 계좌 전체의 위험자산 한도가 없다고 단정할 수는 없습니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- *E-HIGH-RISK-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/0` · label `text` page/slide `1`; charspan `0:118`; bbox `{"b":749.9090909090909,"coord_origin":"BOTTOMLEFT","l":247.0,"r":566.7969999999999,"t":798.0}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1` 인용: “실제 수익률 변동성을 감안 하여 1등급으로 분류하였습니다.” **E-PENSION-CLASS-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/7` · label `table` page/slide `7`; charspan `0:0`; bbox `{"b":394.6044006347656,"coord_origin":"BOTTOMLEFT","l":71.91475677490234,"r":575.2330322265625,"t":779.9194984436035}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1` table cells `r5c1` 인용: “연금저축계좌를 통해 매입이 가능한 집합투자기구입니다.”

**부족 근거·금지 주장**

- *부족 근거** • ‘연금저축 위험자산 비율 제한 없음’을 직접 명시한 제공 문서 근거가 없다. **금지 주장** • 고위험 상품 클래스의 존재만으로 계좌 총량 제한 부재를 추론하지 않는다.

**필수 응답 행동**

- 위험자산 총량 제한 유무를 제공 문서로 확정할 수 없다고 밝힌다.
- 개별 1등급 상품의 매입 가능 사례를 계좌 전체의 한도 부재로 확대해석하지 않는다.

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인: [x] 질문 의도  [x] 목표 답변  [x] 필수 주장  [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 고위험 상품이 연금저축계좌에서 매입 가능하다는 근거는 있으나, 연금저축펀드 계좌 전체의 위험자산 편입 비율 제한 유무를 직접 확인하는 근거는 아님.
  - 따라서 `위험자산 비율 제한 없음` 또는 `제한 있음`을 단정하면 안 됨.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 2. 한투 PROD-008 · 미지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-008` 검색
- 질문: 금 실물을 직접 사는 것과 금 ETF에 투자하는 것은 어떤 차이가 있고, 어느 쪽이 유리한가요?

**목표 답변**

> 제공된 문서에서는 금 실물과 금 ETF의 상품 구조, 실물 인출 방식, 비용 및 과세 차이를 확인할 수 없습니다. 따라서 현재 확인 가능한 자료만으로 두 투자 방식의 차이를 구체적으로 비교하거나 어느 쪽이 더 유리하다고 판단하기는 어렵습니다. 정확한 비교를 위해서는 각 상품의 거래 방식, 비용 및 과세 기준을 확인할 수 있는 추가 자료가 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 금 실물과 금 ETF의 상품 구조 및 과세 근거가 전부 없다. **금지 주장** • 외부 세법 지식으로 빈 근거를 채우지 않는다. • ‘골드플랜’ 펀드명을 금 투자 근거로 오인하지 않는다.

**필수 응답 행동**

- 금 실물과 금 ETF의 구조, 세금, 수수료, 실물 인출 가능 여부, 투자 유불리를 제공 문서만으로 확정할 수 없다고 밝힌다.
- `골드플랜`처럼 이름에 금이 들어간 펀드나 관련 없는 상품명을 금 실물·금 ETF 비교 근거로 사용하지 않는다.
- 어느 쪽이 더 유리하다고 추천하거나 단정하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [ ] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 금 실물과 금 ETF의 구조·비용·과세 차이 및 유불리를 판단할 직접 근거가 없어 `미지원` 판정은 적절함.
  - 다만 목표 답변의 `158개 Docling 번들`과 `정답화`는 내부 평가 용어이므로 사용자 대상 표현으로 수정할 필요가 있음.
  - 확인되지 않은 외부 세법 지식을 추가하지 않고, 제공 자료로는 비교 및 유불리 판단이 어렵다는 한계를 자연스럽게 안내하도록 수정 권장.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [x] 미반영

### 3. 한투 PROD-012 · 미지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-012` 검색
- 질문: IRP 계좌에서 중도인출 등으로 안전자산 비중이 30% 미만으로 떨어지면 어떻게 처리되나요?

**목표 답변**

> 문서는 IRP 일반 위험자산 비중이 전체 적립금의 70% 이내라는 원칙까지만 확인해 줍니다. 중도인출 뒤 안전자산 비중이 30% 미만이 되었을 때 강제매도 여부, 신규매수 제한, 유예기간 또는 복원 절차는 제공 문서에서 확인되지 않으므로 단정할 수 없습니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.” **E-IRP-70-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view) `#/texts/1` · label `section_header` page/slide `2`; charspan `0:28`; bbox `{"b":788.6752770278034,"coord_origin":"BOTTOMLEFT","l":36.0,"r":324.53,"t":800.0399829101564}` 인용: “퇴직연금 적립금의 70% 까지만 투자가능한 운용방법”

**부족 근거·금지 주장**

- *부족 근거** • 안전자산 하한 미달 시 강제매도·매수제한·유예·복원 절차를 정한 항목이 없다. **금지 주장** • 70% 매수 한도에서 30% 하한 복원 메커니즘을 역추론하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인: [x] 질문 의도  [x] 목표 답변  [x] 필수 주장  [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원`보다는 `부분 지원`으로 바꾸는 것이 더 정확해 보임.
  - 전체 적립금이 위험자산과 비위험자산으로 구성된다는 전제에서는 `위험자산 비중 <= 70%`와 `비위험자산 비중 >= 30%`가 사실상 같은 의미이므로, 중도인출 후 안전자산 비중이 30% 미만이면 위험자산 비중이 70%를 초과한 상태로 해석할 수 있음.
  - 다만 문서 근거로 확인되는 것은 `위험자산 70% 한도` 원칙뿐이며, 기존 위험자산 강제매도 여부, 신규매수 제한, 유예기간, 추가 납입 등 비중 복원 절차는 확인되지 않음.
  - 제안 목표 답변: 중도인출 후 비위험자산 비중이 30% 미만이 되었다면, 위험자산과 비위험자산이 전체 적립금을 구성한다는 전제에서 위험자산 비중이 70%를 초과한 상태로 볼 수 있습니다. 제공 문서에서는 IRP의 위험자산 투자 비중이 전체 적립금의 70% 이내로 제한된다는 원칙까지만 확인됩니다. 다만 이 경우 기존 위험자산의 강제매도 여부, 신규매수 제한, 유예기간 또는 비중 복원 절차는 확인되지 않으므로 단정할 수 없습니다.
  - 제안 필수 주장: `PROD-012-C1`: IRP의 위험자산 투자 비중은 전체 적립금의 70% 이내로 제한된다.
  - 주의: `안전자산 30%를 항상 의무적으로 유지해야 한다`고 직접 표현하는 것은 피해야 함. 문서가 직접 말하는 규정은 `위험자산 70% 한도`이고, 안전자산의 정확한 범위와 사후 조치까지는 제시하지 않았기 때문임.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 4. 한투 POLICY-005 · 미지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-005` 검색
- 질문: 연금계좌 연간 납입한도를 다 채우지 못했는데, 남은 한도를 다음 해로 이월해서 쓸 수 있나요?

**목표 답변**

> 제공 문서에는 연금저축·IRP 합산 연간 납입한도가 적혀 있지만, 연금계좌의 미사용 한도를 다음 해로 이월할 수 있는지 여부를 직접 정한 항목은 없습니다. ISA 한도가 이월된다는 문구는 확인되지만 이를 연금계좌에 반대로 적용할 수는 없으므로, 이 문서 집합만으로 ‘이월 불가’를 정답으로 확정할 수 없습니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- *E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.” **E-ISA-CARRY-CONTEXT-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view) `#/texts/15` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` 인용: “ISA는 매년 2천만원까지 입금이 가능한데 한도는 이월되서 누적”

**부족 근거·금지 주장**

- *부족 근거** • 연금계좌 미사용 납입한도의 이월 가능 또는 불가를 직접 명시한 항목이 없다. **금지 주장** • ISA의 이월 규정을 연금계좌 규정으로 전용하지 않는다. • 연간 한도라는 표현만으로 비이월을 추론하지 않는다.

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 연금계좌 미사용 납입한도 이월 가능 여부를 직접 정한 근거가 없고, ISA 이월 규정을 연금계좌에 전용하지 않도록 잘 제한하고 있음.
  - 답변이 `이월 불가`를 단정하지 않아 문서 근거 범위를 지킴.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 5. 한투 POLICY-010 · 미지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-010` 검색
- 질문: ISA 계좌 만기 연장 신청 시점을 놓쳤습니다. 만기가 지난 계좌를 다시 연장할 수 있나요?

**목표 답변**

> 제공 문서에서는 ISA의 만기연장과 재가입이 가능하다는 일반적인 내용은 확인됩니다. 다만 만기연장 신청 시점을 놓쳐 이미 만기가 지난 동일 계좌를 다시 연장할 수 있는지, 별도의 유예기간이나 처리 절차가 있는지는 확인되지 않습니다. 따라서 연장 가능 여부를 단정할 수 없으며, 해당 계좌의 약관과 현재 업무규정을 추가로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- *E-ISA-EXTEND-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view) `#/tables/2` · label `table` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r1c2` 인용: “1인 1개 보유 (만기연장/재가입 가능)” **E-ISA-60-CALENDAR-D6** — [doc6.docx](https://drive.google.com/file/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/view) `#/texts/57` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` 인용: “60일은 캘린더 기준, 만기일자 불산입”

**부족 근거·금지 주장**

- *부족 근거** • 만기 경과 후 연장 가능 여부와 30일 세제혜택 소멸 규정이 없다. **금지 주장** • 연금전환 60일 기한을 만기연장 기한으로 바꾸지 않는다. • 근거 없는 30일 규칙을 생성하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [ ] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 문서에는 ISA의 일반적인 만기연장·재가입 가능성만 제시되어 있으며, 만기 경과 후 동일 계좌의 연장 가능 여부와 신청기한·절차는 확인되지 않으므로 `미지원` 판정은 적절함.
  - 다만 목표 답변에 질문과 직접 관련 없는 연금계좌 전환 60일 기한과 근거 없는 30일 규칙이 포함되어 있어 답변이 복잡하고 혼동될 수 있음.
  - 해당 내용은 부족 근거·금지 주장에만 유지하고, 목표 답변은 만기 경과 후 연장 가능 여부를 확인할 수 없다는 결론에 집중하도록 수정 권장.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [x] 미반영

### 6. 한투 POLICY-012 · 미지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-012` 검색
- 질문: ISA 계좌의 의무가입기간 3년이 되는 날짜가 토요일입니다. 휴일이 낀 경우 해지·재가입 처리는 어떻게 되나요?

**목표 답변**

> 제공 문서에서는 ISA의 만기연장과 재가입이 가능하다는 일반적인 내용은 확인됩니다. 다만 ISA 의무가입기간이 3년이라는 점, 의무가입기간 종료일이 토요일이나 휴일인 경우 어느 영업일에 해지·재가입 처리하는지, 별도의 유예기간이나 처리 절차가 있는지는 확인되지 않습니다. 따라서 휴일이 낀 경우의 해지·재가입 처리 방식을 단정할 수 없으며, 해당 계좌의 약관과 현재 업무규정을 추가로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- *E-ISA-EXTEND-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view) `#/tables/2` · label `table` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r1c2` 인용: “1인 1개 보유 (만기연장/재가입 가능)”

**부족 근거·금지 주장**

- *부족 근거** • ISA 만기일이 휴일일 때 적용할 영업일 산정 규칙이 없다. **금지 주장** • 디폴트옵션 등 다른 제도의 휴일 규칙을 ISA에 전용하지 않는다. • 직전 또는 다음 영업일을 근거 없이 선택하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [ ] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 근거는 `1인 1개 보유 (만기연장/재가입 가능)`뿐이므로 ISA 만기연장·재가입 가능성만 부분적으로 뒷받침함.
  - `ISA 의무가입기간 3년`은 첨부 근거로 직접 확인되지 않으므로 목표 답변에서 근거 있는 내용처럼 표현하면 안 됨.
  - 휴일이 낀 경우의 해지·재가입 처리 방식도 확인되지 않으므로 `미지원` 판정은 유지하는 것이 적절함.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [x] 미반영

### 7. 한투 POLICY-015 · 최신성 공백

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-015` 검색
- 질문: 예전에 있었던 소득공제 장기펀드 같은 상품이 지금도 있나요? 지금은 어떤 상품으로 세액공제를 받을 수 있나요?

**목표 답변**

> 제공 자료만으로는 소득공제 장기펀드의 제도 종료 시점이나 2026년 현재 신규가입 가능 여부를 확인할 수 없습니다. 따라서 과거 상품명이 자료에 등장한다는 이유만으로 현재도 가입할 수 있다고 판단해서는 안 됩니다. 한편 제공 자료에서는 연금저축과 IRP 납입을 세액공제 대상으로 설명하고 있으며, 세액공제 대상 납입한도는 연금저축이 연 600만 원, IRP는 연금저축 납입액을 포함하여 합산 연 900만 원으로 제시됩니다. 현재 적용 가능 여부와 구체적인 기준은 해당 연도의 규정을 추가로 확인해야 합니다.

**필수 주장**

- **C1** 제공 문서에서는 연금저축과 IRP 납입을 세액공제 대상으로 설명한다.
  - 근거: E-PENSION-CREDIT-D41
- **C2** 제공 문서상 세액공제 대상 납입한도는 연금저축 연 600만 원, IRP는 연금저축 납입액을 포함하여 합산 연 900만 원이다.
  - 근거: E-PENSION-LIMITS-D41

**문서 근거·주의점**

- *E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/3` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.” **E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.”

**부족 근거·금지 주장**

- *부족 근거** • 소득공제 장기펀드의 종료 시점과 2026년 신규가입 가능 여부를 직접 확인할 최신 문서가 없다. **금지 주장** • 근거 없이 2015년 종료를 확정하지 않는다. • 과거 상품명 노출을 현재 판매 가능성으로 해석하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [ ] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 소득공제 장기펀드의 현재 신규가입 가능 여부와 제도 종료 시점은 최신 문서로 확인되지 않으므로 `최신성 공백` 판정이 적절함.
  - 반면 연금저축·IRP의 세액공제 대상 여부와 납입한도는 제시된 근거로 직접 확인됨.
  - 목표 답변의 기존 내부 처리 용어는 사용자 대상 표현인 `제공 자료`로 변경하는 것을 권장함.
  - 사용자가 언급하지 않은 `2015년 폐지` 주장은 목표 답변보다 금지 주장에만 두는 것이 자연스러움.
  - `실제 적용은 소득에 따라 달라진다`는 내용은 현재 제시된 인용에서 직접 확인되지 않으므로, 별도 근거가 없다면 삭제하거나 최신 규정 확인이 필요하다는 표현으로 제한할 것을 권장함.
  - 필수 주장은 `세액공제 대상 여부`와 `600만 원·900만 원 한도`를 각각 평가할 수 있도록 C1·C2로 분리 권장.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [x] 미반영

## 2차: 한투 부분 지원 14개 (14개)

### 8. 한투 PROD-001 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-001` 검색
- 질문: IRP 계좌에 현금성 자산이 있는데 이걸 펀드로 투자하려니 실제 매수 가능 금액이 훨씬 적게 나옵니다. 왜 그런가요?

**목표 답변**

> 펀드라고 해서 모두 위험자산으로 분류되는 것은 아니므로, 현재 정보만으로 실제 매수 가능 금액이 적게 표시되는 정확한 원인을 확정하기는 어렵습니다. 매수하려는 펀드가 위험자산으로 분류되는 경우에는 IRP의 위험자산 투자 비중이 전체 적립금의 70% 이내로 제한되므로, 현금성자산이 충분하더라도 남아 있는 위험자산 한도까지만 매수할 수 있습니다. 반면 해당 펀드가 비위험자산이라면 이 70% 제한만으로는 매수 가능 금액이 적은 이유를 설명할 수 없습니다. 정확한 원인을 확인하려면 해당 펀드의 위험자산 분류, 현재 위험자산 보유비중 및 계좌의 매수가능액 산정 내역을 확인해야 합니다.

**필수 주장**

- **C1·DIRECT** IRP의 위험자산 투자 비중은 전체 적립금의 70% 이내다.
  - 근거: E-IRP-70-D14, E-IRP-70-D58

**필수 응답 행동**

- 매수하려는 펀드가 위험자산이라고 단정하지 않는다.
- 위험자산으로 분류되는 경우에만 70% 제한을 가능한 원인으로 제시한다.
- 비위험자산이라면 70% 제한으로 설명할 수 없다고 구분한다.
- 현재 자료만으로 실제 계좌의 정확한 원인은 확정하지 않는다.

**문서 근거·주의점**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.” **E-IRP-70-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view) `#/texts/1` · label `section_header` page/slide `2`; charspan `0:28`; bbox `{"b":788.6752770278034,"coord_origin":"BOTTOMLEFT","l":36.0,"r":324.53,"t":800.0399829101564}` 인용: “퇴직연금 적립금의 70% 까지만 투자가능한 운용방법”

**부족 근거·금지 주장**

- *부족 근거** • 개별 계좌의 현재 위험자산 비중, 주문가능금액 산식과 대상 펀드 분류가 없다. **금지 주장** • 70% 한도가 유일한 원인이라고 단정하지 않는다. • 현금성자산의 30%가 항상 매수가능하다고 계산하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [ ] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 질문에는 매수 대상 펀드의 위험자산 분류가 제시되지 않았으므로 위험자산 70% 제한을 실제 원인처럼 중심적으로 설명해서는 안 됨.
  - 정확한 원인을 확정할 수 없다는 한계를 먼저 밝히고, 위험자산인 경우와 그렇지 않은 경우를 한 답변 안에서 조건부로 구분하도록 수정 필요.
  - 멀티턴을 지원하지 않으므로 역질문 대신 사용자가 확인해야 할 펀드 분류·현재 위험자산 비중·매수가능액 산정 내역을 함께 안내할 것.
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [x] 미반영

### 9. 한투 PROD-003 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-003` 검색
- 질문: IRP 계좌에서 국채 ETF를 보유 중인데 평가금액이 계속 줄어듭니다. 국채 ETF는 어떤 상품인가요?

**목표 답변**

> ETF는 지수형 펀드의 성격과 거래소에서 실시간 거래되는 성격을 함께 갖습니다. 국채를 담은 ETF도 시장가격이 변하는 실적배당상품이며, 문서상 채권은 시장금리가 오르면 가격이 내려가 원금손실이 날 수 있습니다. 잔존만기가 긴 채권일수록 금리변동의 영향이 큰 경향도 있습니다. 따라서 평가금액 하락은 금리와 기초채권 가격 변화에 관련될 수 있지만, 보유 종목과 매수시점 정보 없이 정확한 하락 원인을 특정할 수는 없습니다.

**필수 주장**

- *C1** ETF는 인덱스 펀드와 거래소 실시간 거래의 성격을 함께 가진다. 근거: E-ETF-STRUCTURE-D53 **C2** 금리 상승은 채권가치 하락과 원금손실 가능성을 만든다. 근거: E-BOND-RATE-R2B **C3** 잔존만기가 긴 채권은 금리변동 영향을 더 크게 받는 경향이 있다. 근거: E-BOND-DURATION-R2C

**문서 근거·주의점**

- *E-ETF-STRUCTURE-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/8` · label `list_item` page/slide `1`; charspan `0:74`; bbox `{"b":461.0464534983916,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.5385599999998,"t":492.1419829101563}` 인용: “인덱스 펀드의 장점과 거래소에 상장되어 실시간으 로 거래되는 주식의 장점을 모두 갖춘 펀드” **E-BOND-RATE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/43` · label `table` page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` table cells `r3c1` 인용: “시장이자율이 상승하는 경우 채권가격을 결정하는 할인율이 함께 상승함에 따라 그 가치가 하락” **E-BOND-DURATION-R2C** — [R2_KR5144420020.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/6` · label `table` page/slide `7`; charspan `0:0`; bbox `{"b":64.49822998046875,"coord_origin":"BOTTOMLEFT","l":48.67829513549805,"r":555.131591796875,"t":788.495174407959}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5144420020--f65b36a28194--docling-no-ocr-native-v1` table cells `r4c2` 인용: “잔존만기가 긴 장기채권은 단기채권보다 금리에 영향을 많이 받으며”

**부족 근거·금지 주장**

- *부족 근거** • 고객 보유 ETF의 종목, 듀레이션, 매수시점과 실제 가격 경로가 없다. **금지 주장** • 평가손실의 원인을 금리 하나로 확정하지 않는다. • 국채 ETF를 원금보장상품으로 표현하지 않는다.

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `부분 지원` 유지가 적절함.
  - ETF 구조, 금리 상승 시 채권가격 하락, 장기채권의 금리 민감도는 근거로 뒷받침됨.
  - 보유 종목·매수시점 없이 정확한 하락 원인을 특정하지 않아 답변 한계도 적절함.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 10. 한투 PROD-006 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-006` 검색
- 질문: 연금저축계좌와 IRP계좌는 투자할 수 있는 상품이나 투자비율 제한이 어떻게 다른가요?

**목표 답변**

> IRP는 ETF·펀드·채권 등을 운용할 수 있고 일반 위험자산은 전체 적립금의 70% 이내라는 점이 문서에서 확인됩니다. 연금저축은 매우 높은 위험 등급의 연금저축용 펀드 클래스가 실제로 존재한다는 점까지 확인됩니다. 그러나 제공 문서에는 연금저축의 전체 투자가능 상품군과 위험자산 총량 제한 유무를 직접 명시한 비교 규정이 없어 그 차이까지 단정한 완전 비교는 할 수 없습니다.

**필수 주장**

- *C1** IRP는 ETF·펀드·채권 등을 운용하며 일반 위험자산은 70% 이내다. 근거: E-IRP-70-D14 **C2** 1등급 상품에 연금저축계좌 매입 가능 클래스가 존재한다. 근거: E-HIGH-RISK-R2A, E-PENSION-CLASS-R2A

**문서 근거·주의점**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.” **E-HIGH-RISK-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/0` · label `text` page/slide `1`; charspan `0:118`; bbox `{"b":749.9090909090909,"coord_origin":"BOTTOMLEFT","l":247.0,"r":566.7969999999999,"t":798.0}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1` 인용: “실제 수익률 변동성을 감안 하여 1등급으로 분류하였습니다.” **E-PENSION-CLASS-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/7` · label `table` page/slide `7`; charspan `0:0`; bbox `{"b":394.6044006347656,"coord_origin":"BOTTOMLEFT","l":71.91475677490234,"r":575.2330322265625,"t":779.9194984436035}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1` table cells `r5c1` 인용: “연금저축계좌를 통해 매입이 가능한 집합투자기구입니다.”

**부족 근거·금지 주장**

- *부족 근거** • 연금저축 전체 상품군과 계좌 수준 위험자산 총량 규정이 없다. **금지 주장** • 연금저축에는 위험자산 제한이 없다고 단정하지 않는다. • 고위험 클래스 하나를 전체 상품군으로 일반화하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 11. 한투 PROD-007 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-007` 검색
- 질문: 연금저축, IRP, 퇴직연금(DC) 계좌 중 어느 계좌가 담보대출이 가능한가요?

**목표 답변**

> 문서에서 직접 확인되는 것은 해당 회사의 연금저축·개인연금저축계좌 증권담보융자입니다. 계좌 안의 보유 펀드를 담보로 회사가 정한 융자비율에 따라 대출하며, 해당 연금저축계좌의 약정 가능도 명시합니다. 반면 IRP·DC 자료에는 기존 담보대출 원리금 상환을 위한 중도인출 맥락만 있어 신규 담보대출 가능 또는 불가를 직접 정하지 않습니다. 따라서 연금저축은 이 회사 문서 기준으로 가능하다고 답할 수 있지만, IRP·DC와 다른 금융회사의 최신 취급 여부는 별도 확인해야 합니다.

**필수 주장**

- *C1** 해당 회사 문서상 연금저축·개인연금저축계좌의 보유 펀드를 담보로 대출할 수 있다. 근거: E-PENSION-COLLATERAL-D3, E-PENSION-COLLATERAL-ELIGIBLE-D3

**문서 근거·주의점**

- *E-PENSION-COLLATERAL-D3** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view) `#/texts/2` · label `list_item` page/slide `1`; charspan `0:54`; bbox `{"b":721.3733113606771,"coord_origin":"BOTTOMLEFT","l":54.66666666666667,"r":464.0,"t":736.0399780273438}` retrieval `knowledge-243434ee0061-0000` 인용: “연금저축계좌 및 개인연금저축계좌 내 보유한 편드틀 담보로 당사에서 지정한 움자비울에 따라 대출실행” **E-PENSION-COLLATERAL-ELIGIBLE-D3** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view) `#/texts/7` · label `list_item` page/slide `1`; charspan `0:26`; bbox `{"b":584.0399780273438,"coord_origin":"BOTTOMLEFT","l":53.0,"r":238.33333333333334,"t":598.7066446940104}` retrieval `knowledge-243434ee0061-0001` 인용: “당사 연금저축(개인연금저축)계좌 약정 가능” **E-COLLATERAL-CONTEXT-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view) `#/tables/0` · label `table` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847` table cells `r6c0` 인용: “퇴직연금제도를 받을 권리를 담보로 제공하고 대출받은 가입자가 그 대출 원리금을 상환하기 위한 경우” **E-COLLATERAL-CONTEXT-D55** — [doc55.docx](https://drive.google.com/file/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/view) `#/texts/383` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “퇴직연금(DB/DC) 적립금을 담보로 대출받은 금액을 상환”

**부족 근거·금지 주장**

- *부족 근거** • IRP·DC의 신규 담보대출 가능·불가와 금융회사별 최신 취급 여부를 직접 정한 항목이 없다. • 최종 배포 no-OCR 번들에서는 doc3 본문이 탈락해 로컬 OCR Docling 객체·원본 PDF 렌더·검색 청크를 교차검증했다. **금지 주장** • 상환 사유의 존재를 IRP·DC의 신규 담보대출 가능성으로 바꾸어 말하지 않는다. • 한 회사의 연금저축 취급 문서를 전 금융회사에 일반화하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 12. 한투 PROD-010 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-010` 검색
- 질문: 퇴직을 앞두고 있고 퇴직금이 크게 들어올 예정입니다. IRP 계좌에서 매년 일정 수익률을 목표로 포트폴리오를 어떻게 구성하면 좋을까요?

**목표 답변**

> 어떤 투자전략이나 성과목표도 반드시 실현된다고 보장되지 않고 과거 실적도 미래 성과를 보장하지 않습니다. 상품의 위험등급과 본인의 투자경력·투자성향을 확인해야 하므로, ‘매년 일정 수익률’만으로 특정 비중의 포트폴리오를 정할 수 없습니다. 투자기간, 손실 감내수준과 필요한 현금흐름을 먼저 정해야 하며, IRP 일반 위험자산은 전체 적립금의 70% 이내라는 제약도 반영해야 합니다.

**필수 주장**

- *C1** 성과목표와 과거 실적은 미래 성과를 보장하지 않는다. 근거: E-NO-GUARANTEE-R2B **C2** 투자경력과 투자성향에 맞는지 확인해야 한다. 근거: E-SUITABILITY-R2B **C3** IRP 일반 위험자산은 70% 이내다. 근거: E-IRP-70-D14

**문서 근거·주의점**

- *E-NO-GUARANTEE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/33` · label `list_item` page/slide `2`; charspan `0:97`; bbox `{"b":575.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":524.3420000000001,"t":598.0}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` 인용: “성과목표는 반드시 실현된다는 보장은 없습니다.” **E-SUITABILITY-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/32` · label `list_item` page/slide `2`; charspan `0:95`; bbox `{"b":631.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":525.676,"t":654.0}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` 인용: “투 자경력이나 투자성향에 적합한 상품인지 신중한 투자결정을 하시기 바랍니다.” **E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”

**부족 근거·금지 주장**

- *부족 근거** • 투자기간, 위험성향, 현금흐름과 고객별 손실 감내수준이 없다. **금지 주장** • 목표수익률 달성을 보장하지 않는다. • 고객 정보 없이 구체적 비중이나 종목을 추천하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 13. 한투 PROD-011 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-011` 검색
- 질문: 여유자금이 있는데 몇 년간 안정적으로 운용할 수 있는 상품을 추천해주세요. 절세 상품도 활용하고 싶습니다

**목표 답변**

> 현재 정보만으로 특정 상품을 추천할 수는 없습니다. 문서가 퇴직연금에서 100% 투자가능한 대표 운용방법으로 제시한 항목에는 예적금, GIC, RP, 국채·통안채·정부보증채권과 MMF 등이 있습니다. 연금계좌 납입에는 세액공제 혜택이 있지만, IRP는 법정 사유가 아니면 부분 인출이 제한될 수 있으므로 몇 년 뒤 쓸 돈인지와 유동성 필요를 먼저 확인해야 합니다. 상품 선택은 투자기간과 손실 감내수준을 확인한 뒤 해야 합니다.

**필수 주장**

- *C1** 문서상 100% 투자 가능 대표 운용방법에 예적금·GIC·RP·일부 채권·MMF 등이 있다. 근거: E-IRP-SAFE-D58 **C2** 연금계좌 납입에는 세액공제 혜택이 있다. 근거: E-PENSION-CREDIT-D41 **C3** IRP 부분 인출은 법정 사유에 의해 제한된다. 근거: E-IRP-LIQUIDITY-D41

**문서 근거·주의점**

- *E-IRP-SAFE-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view) `#/tables/0` · label `table` page/slide `1`; charspan `0:0`; bbox `{"b":179.88836669921875,"coord_origin":"BOTTOMLEFT","l":35.43013381958008,"r":557.422119140625,"t":775.9032516479492}` table cells `r1c1, r2c1, r3c1, r4c1, r10c1, r12c1, r13c1` 인용: “은행 및 우체국 예금 / 적금” **E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/3` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.” **E-IRP-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/12` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0001` 인용: “반면 IRP는 무주택자의 주택 구입 등 법정 사유를 충족해야 부분 인출이 가능해 까다롭다. IRP로만 운용하다 일부 금액이 필요한데 법정사유에 해당되지 않으면 전체를 해지해야 되서 불이익이 크다.” **E-SUITABILITY-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/32` · label `list_item` page/slide `2`; charspan `0:95`; bbox `{"b":631.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":525.676,"t":654.0}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` 인용: “투 자경력이나 투자성향에 적합한 상품인지 신중한 투자결정을 하시기 바랍니다.”

**부족 근거·금지 주장**

- *부족 근거** • 고객의 기간, 거주·소득·세액공제 가능성, 위험성향과 유동성 필요가 없다. **금지 주장** • 특정 종목을 단정 추천하지 않는다. • 세액공제가 모두에게 동일하게 적용된다고 말하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 14. 한투 PROD-013 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-013` 검색
- 질문: 연금계좌에서 기타 ETF(채권형 등)의 분배금을 받았는데, 이미 한 번 과세된 뒤 나중에 연금소득세를 또 내는 이중과세 문제가 있다고 들었습니다. 지금은 어떻게 처리되나요?

**목표 답변**

> 연금계좌의 운용수익은 기본적으로 인출 전까지 과세이연됩니다. 다만 해외 배당·이자에 외국납부세액이 붙는 펀드·ETF는 문서상 2025년 1월 1일부터 종전의 선환급 단계가 없어져 세후 금액을 받게 되고 그만큼 과세이연 효과가 낮아질 수 있습니다. 이 근거는 외국납부세액이 있는 해외 투자분에 관한 것이므로, 모든 채권형·기타 ETF가 동일하게 이중과세된다고 결론낼 수 없습니다. 상품의 투자대상과 외국 원천징수 여부를 먼저 확인해야 합니다.

**필수 주장**

- *C1** 연금계좌 운용수익은 기본적으로 과세이연된다. 근거: E-ETF-PENSION-TAX-D43 **C2** 2025년부터 외국납부세액 선환급 단계가 사라져 과세이연 효과가 낮아질 수 있다. 근거: E-FOREIGN-TAX-2025-D42, E-FOREIGN-DEFERRAL-D36

**문서 근거·주의점**

- *E-ETF-PENSION-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view) `#/texts/20` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112` retrieval `knowledge-f146981691bb-0002` 인용: “해외주식형 월배당 ETF와 그 밖의 ETF의 경우 매매차익과 분배금 모두 과세가 이연된다.” **E-FOREIGN-TAX-2025-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view) `#/texts/19` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185` retrieval `knowledge-40ff19a261a2-0004` 인용: “2025년 이후(2025.1.1~)부터는 개정세법이 적용되어 국세청이 세액을 먼저 환급해주는 단계가 사라졌다.” **E-FOREIGN-DEFERRAL-D36** — [doc36.docx](https://drive.google.com/file/d/1FwipZvxX_ogEbmySP03Tgz7Q7DIBsLfF/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `9647f457ae3130d224642ee23d2284094b33568f2c3bb49542384039b49b6fe1` · Docling JSON SHA-256 `36b46f60be09cb40936a5b90df123ba668356645984b21beb735f737d8d979b0` 인용: “외국납부세액이 발생하는 펀드/ETF 등에 투자한다면 과세이연 효과가 낮아질 수 있다”

**부족 근거·금지 주장**

- *부족 근거** • 질문 속 ETF의 투자대상과 실제 원천징수 내역, 2025년 이후 추가 개정 여부가 없다. **금지 주장** • 모든 기타 ETF에 동일한 이중과세가 발생한다고 일반화하지 않는다. • 최종 세액을 상품정보 없이 계산하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 15. 한투 PROD-014 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-014` 검색
- 질문: 달러로 투자하는 채권 상품에 투자했는데, 원화 평가금액이 마이너스로 보입니다. 실제로 손해를 본 건가요?

**목표 답변**

> 원화 평가금액이 마이너스라는 표시만으로 손실 원인을 하나로 단정할 수 없습니다. 환헤지하지 않은 외화자산은 자산 자체가 올라도 원화가 외국통화보다 강해지면 원화 환산가치가 낮아질 수 있고, 채권 자체도 시장금리가 오르면 가격이 내려갈 수 있습니다. 따라서 환율과 채권가격 요인이 함께 작용할 수 있으며, 실제 확정손익 판단에는 매입가격·현재 채권가격·적용환율·매도나 환전 여부가 필요합니다.

**필수 주장**

- *C1** 환헤지하지 않은 외화자산은 원화 강세 때 원화 환산가치가 낮아질 수 있다. 근거: E-FX-RISK-R2B **C2** 시장금리 상승은 채권가치 하락을 만들 수 있다. 근거: E-BOND-RATE-R2B

**문서 근거·주의점**

- *E-FX-RISK-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/43` · label `table` page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` table cells `r6c1` 인용: “원화의 가치가 외국통화에 비하여 상대적으로 더 높아지면, 외화자산인 투자자산의 가치는 원화가치로 환산했을 때 낮아집니다.” **E-BOND-RATE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/43` · label `table` page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1` table cells `r3c1` 인용: “시장이자율이 상승하는 경우 채권가격을 결정하는 할인율이 함께 상승함에 따라 그 가치가 하락”

**부족 근거·금지 주장**

- *부족 근거** • 계좌 화면의 평가손익 정의, 매입가격·환율·현재가와 실현 거래가 없다. **금지 주장** • 환전 전에는 손해가 아니라고 절대화하지 않는다. • 환율만을 유일한 원인으로 확정하지 않는다.

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `부분 지원` 유지가 적절함.
  - 환율과 채권가격 요인이 함께 작용할 수 있다는 설명은 근거 범위에 맞고, 실제 확정손익은 계좌 정보가 필요하다고 제한하고 있음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 16. 한투 PROD-015 · 부분 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-015` 검색
- 질문: 배당이 나오는 해외 ETF에 투자하려고 합니다. 배당금이 나오면 자동으로 재투자되는 기능이 있나요? 그리고 이런 상품은 연금계좌 등 어떤 계좌에서 투자할 수 있나요?

**목표 답변**

> 문서는 연금저축·IRP에서 국내에 상장된 해외 ETF에 투자하는 경우를 확인해 줍니다. 반면 해외 거래소 상장 ETF를 직접 거래할 수 있는 연금계좌가 무엇인지, 배당금을 자동으로 같은 ETF에 재투자하는 회사 서비스가 있는지는 확인해 주지 않습니다. 국내상장 상품인지 해외상장 직접투자 상품인지 먼저 구분하고, 자동재투자 기능과 현재 거래가능 계좌는 회사의 최신 서비스·상품 목록에서 확인해야 합니다.

**필수 주장**

- *C1** 연금저축·IRP에서 국내상장 해외 ETF 투자와 과세이연이 문서화되어 있다. 근거: E-OVERSEAS-ETF-D42 **C2** 퇴직연금 거래가능 ETF는 최신 목록에서 확인해야 한다. 근거: E-ETF-LIVE-LIST-D53

**문서 근거·주의점**

- *E-OVERSEAS-ETF-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view) `#/texts/15` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185` 인용: “국내 상장 해외 ETF에 투자 시 과세이연효과가 있다.” **E-ETF-LIVE-LIST-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/11` · label `list_item` page/slide `1`; charspan `0:194`; bbox `{"b":293.26645349839157,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.54,"t":365.4019829101563}` 인용: “퇴직연금에서 거래가능한 ETF 는 홈페지지 , MTS(M STOCK) 에서 확인 가능”

**부족 근거·금지 주장**

- *부족 근거** • 해외상장 ETF 직접거래 가능 계좌와 회사의 배당 자동재투자 서비스 규칙이 없다. **금지 주장** • 펀드 내부 분배금 재투자 조항을 증권계좌 DRIP 서비스로 오인하지 않는다. • 국내상장 해외 ETF와 해외상장 ETF를 혼동하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 17. 한투 POLICY-001 · 부분 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-001` 검색
- 질문: 연금저축계좌에 올해 한도보다 많은 금액을 실수로 입금했습니다. 페널티 없이 뺄 방법이 있을까요?

**목표 답변**

> 먼저 초과분이 세액공제를 받지 않은 납입원금인지 확인해야 합니다. 문서상 세액공제를 받지 않은 납입금은 인출순서상 먼저 빠지고 비과세이며, 연금저축펀드는 필요한 금액을 부분 인출할 수 있습니다. 다만 ‘올해 넣은 초과분이면 모두 페널티 없음’이라는 별도 규정과 상품별 수수료는 문서에서 확인되지 않으므로, 해당 금액의 세액공제 반영 여부와 과세재원 구분을 확인한 뒤 인출해야 합니다.

**필수 주장**

- *C1** 세액공제를 받지 않은 납입금은 먼저 인출되고 비과세다. 근거: E-NONDEDUCTED-WITHDRAW-D44, E-NONDEDUCTED-TAXFREE-D39 **C2** 연금저축펀드는 부분 인출이 가능하나 과세재원에는 세금이 적용될 수 있다. 근거: E-LIQUIDITY-D41

**문서 근거·주의점**

- *E-NONDEDUCTED-WITHDRAW-D44** — [doc44.docx](https://drive.google.com/file/d/1fzuDWMXAYHGdgeClu3l0gUhZkr9KGiKY/view) `#/texts/8` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `09fa92de548b4cf1fb2ba1bfa0115bdbccf33c237626ed668bf58c758a249ed0` · Docling JSON SHA-256 `f7bbf4b8ae33cb1afd5def53d444c208b8723be428b188d774501c479c6f3719` retrieval `knowledge-09fa92de548b-0001` 인용: “세액공제받지 않은 납입금은 비과세되는데 제일 먼저 인출된다.” **E-NONDEDUCTED-TAXFREE-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view) `#/texts/16` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` 인용: “세액공제를 받지 않은 납입금(ISA전환금 포함)이 있을 경우 인출할 때에도 전액 비과세” **E-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/12` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0001` 인용: “연금저축펀드는 부분 인출이 자유롭다. 원할 때 필요한 금액을 인출할 수 있다. 물론 인출금액이 과세재원이면 16.5% 기타소득세가 적용된다.”

**부족 근거·금지 주장**

- *부족 근거** • 당해연도 초과입금 자체를 별도 면책하는 규정과 상품별 수수료가 없다. **금지 주장** • 당해연도 납입금 전부를 무조건 무세금 인출 가능하다고 말하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 18. 한투 POLICY-004 · 부분 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-004` 검색
- 질문: 사업자등록번호가 없는 프리랜서인데 IRP 계좌를 개설할 수 있나요? 가능하다면 어떤 서류가 필요한가요?

**목표 답변**

> 문서상 IRP 가입대상에는 자영업자가 포함됩니다. 그러나 사업자등록번호가 없는 프리랜서를 어떤 자격으로 판단하는지와 건강보험자격득실확인서·소득금액증명원 같은 대체서류 목록은 제공 문서에서 확인되지 않습니다. 따라서 소득·근로 형태를 확인한 뒤 현재 회사의 계좌개설 자격 및 대체 증빙서류 안내를 별도로 확인해야 합니다.

**필수 주장**

- *C1** IRP 가입대상에 자영업자가 포함된다. 근거: E-SELF-EMPLOYED-D14, E-PENSION-ELIGIBILITY-D41

**문서 근거·주의점**

- *E-SELF-EMPLOYED-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/tables/0` · label `table` page/slide `1`; charspan `0:0`; bbox `{"b":126.7911376953125,"coord_origin":"BOTTOMLEFT","l":62.790504455566406,"r":547.125,"t":355.3334045410156}` table cells `r2c0` 인용: “①자영업자” **E-PENSION-ELIGIBILITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/5` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` 인용: “IRP는 직장인, 자영업자, 직역연금가입자 등 가입대상이 정해져 있다.”

**부족 근거·금지 주장**

- *부족 근거** • 무등록 프리랜서의 자격판정과 대체 증빙서류 목록이 없다. **금지 주장** • 문서에 없는 대체서류 목록을 생성하지 않는다. • 자영업자라는 표현만으로 모든 프리랜서 가입을 확정하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 19. 한투 POLICY-008 · 부분 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-008` 검색
- 질문: 다른 증권사 CMA 계좌에 있는 자금을 우리 회사 CMA 계좌로 이체하면 연말정산 세액공제 대상 금액에 영향이 있나요?

**목표 답변**

> 제공 문서가 세액공제 대상으로 설명하는 것은 연금저축·IRP 같은 연금계좌의 납입액입니다. 따라서 일반 CMA끼리의 자금 이동을 연금계좌 납입 세액공제액으로 잡을 근거는 없습니다. 다만 CMA 이체와 세액공제의 무관성을 직접 명시한 문서는 없으므로, 실제 세액공제 대상액은 해당 과세기간의 연금저축·IRP 납입 내역으로 확인해야 합니다.

**필수 주장**

- *C1** 문서상 세액공제는 연금계좌 납입액을 기준으로 설명된다. 근거: E-PENSION-CREDIT-D41, E-PENSION-LIMITS-D41

**문서 근거·주의점**

- *E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/3` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.” **E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.”

**부족 근거·금지 주장**

- *부족 근거** • CMA 간 이체가 세액공제에 미치는 영향을 직접 명시한 항목은 없다. **금지 주장** • CMA를 연금계좌로 취급하지 않는다. • 개인별 공제액을 납입 내역 없이 계산하지 않는다.

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `부분 지원` 유지가 적절함.
  - 제공 문서상 세액공제 대상은 연금저축·IRP 납입액이라는 점을 기준으로 일반 CMA 간 이체를 세액공제 납입으로 보지 않도록 잘 제한하고 있음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 20. 한투 POLICY-009 · 부분 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-009` 검색
- 질문: 연금계좌에 넣은 돈에 대해 세액공제를 아예 신청하지 않으면, 나중에 연금으로 받을 때 연금소득세도 안 내도 된다고 들었습니다. 맞나요?

**목표 답변**

> 세액공제를 받지 않은 납입원금은 인출할 때 비과세라는 설명은 맞지만, 계좌의 운용수익이나 세액공제를 받은 재원까지 모두 비과세가 되는 것은 아닙니다. 또한 문서에는 DC·IRP 과세재원 확정을 위해 국세청 ‘연금보험료등 소득·세액공제확인서’를 제출하고 내점 처리하는 절차가 기재되어 있어 자동 반영이라고 단정할 수 없습니다. 다만 이 절차를 모든 연금저축계좌에 그대로 적용할 근거는 부족하므로 계좌 유형별 과세제외 처리 절차를 확인해야 합니다.

**필수 주장**

- *C1** 세액공제를 받지 않은 납입원금은 인출 시 비과세다. 근거: E-NONDEDUCTED-TAXFREE-D39 **C2** DC·IRP 과세재원 확정에는 국세청 확인서와 내점 절차가 문서화되어 있다. 근거: E-NONTAX-PROCESS-D19, E-NONTAX-DOCUMENT-D19, E-NONTAX-INPERSON-D19

**문서 근거·주의점**

- *E-NONDEDUCTED-TAXFREE-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view) `#/texts/16` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` 인용: “세액공제를 받지 않은 납입금(ISA전환금 포함)이 있을 경우 인출할 때에도 전액 비과세” **E-NONTAX-PROCESS-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view) `#/texts/3` · label `text` page/slide `1`; charspan `0:44`; bbox `{"b":670.5152770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":477.72592000000003,"t":679.9479829101563}` 인용: “초과하는 과세대상금액을 과세제외함으로써 과세대상금액을 일치시켜주는 업무입니다 .” **E-NONTAX-DOCUMENT-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view) `#/texts/6` · label `text` page/slide `1`; charspan `0:28`; bbox `{"b":545.2052770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":292.99592,"t":554.6379829101562}` 인용: “연금보험료등 소득·세액공제확인서 ( 국세청자료 )” **E-NONTAX-INPERSON-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view) `#/texts/8` · label `text` page/slide `1`; charspan `0:6`; bbox `{"b":491.92527702780336,"coord_origin":"BOTTOMLEFT","l":131.78,"r":186.74,"t":501.3579829101563}` 인용: “내점만 가능”

**부족 근거·금지 주장**

- *부족 근거** • doc19의 DC·IRP 절차를 일반 연금저축까지 동일 적용한다는 근거가 없다. **금지 주장** • 세액공제 미신청만으로 계좌의 모든 재원이 비과세라고 말하지 않는다. • 모든 계좌에 자동 과세제외가 된다고 말하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 21. 한투 POLICY-011 · 부분 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-011` 검색
- 질문: 오래전(2013년 이전)에 가입한 연금계좌를 다른 금융회사로 이전하려고 합니다. 가입일을 그대로 승계받으면 연금수령연차 계산에서 유리하다고 들었는데, 어떤 조건에서 그렇게 되나요?

**목표 답변**

> 문서상 정확한 기준일은 2013년 3월 1일입니다. 그 이전 가입 연금계좌는 연금수령연차를 6년차부터 기산합니다. 또 2013년 3월 1일 이전 DC·DB 가입자는 퇴직금 전액을 신규 연금계좌로 이체하는 경우에 한해 6년차 특례를 적용받을 수 있다고 설명합니다. 그러나 일반적인 금융회사 간 연금계좌 이전 때 원래 가입일이 어떤 조건으로 승계되는지는 제공 문서에 없어, 해당 이전계약의 가입일 승계 여부를 별도로 확인해야 합니다.

**필수 주장**

- *C1** 2013년 3월 1일 이전 가입 연금계좌는 연금수령연차를 6년차부터 기산한다. 근거: E-OLD-PENSION-YEAR-D39 **C2** 2013년 3월 1일 이전 DC·DB는 퇴직금 전액을 신규 연금계좌로 이체할 때 특례가 적용된다. 근거: E-OLD-DC-TRANSFER-D39

**문서 근거·주의점**

- *E-OLD-PENSION-YEAR-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view) `#/texts/11` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` 인용: “2013년 3월 1일 이전 가입한 연금계좌는 6년차로 기산한다.” **E-OLD-DC-TRANSFER-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view) `#/texts/12` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` 인용: “DC/DB 퇴직금 전액을 신규 연금계좌로 이체하는 경우에 한하여 6년차 특례”

**부족 근거·금지 주장**

- *부족 근거** • 일반 금융회사 간 계약이전의 가입일 승계 조건이 없다. **금지 주장** • 모든 이전에서 가입일이 자동 승계된다고 말하지 않는다. • 기준일을 2013년 1월 1일 등으로 바꾸지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

## 3차: 미래에셋 미지원 21개 (21개)

### 22. 미래에셋 MA-PP-002 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-002` 검색
- 질문: [개인연금] 보험사에 있는 내 연금, 미래에셋증권으로 가져올 수 있나요?

**목표 답변**

> 제공 문서에는 보험사의 어떤 연금상품이 미래에셋증권으로 이전 가능한지, 세제적격·비적격 판별 기준과 현재 수관 가능 여부가 제시되어 있지 않습니다. 상품명만으로 가능 여부를 단정하지 말고, 기존 보험계약의 세제 구분과 미래에셋증권의 수관 가능 여부를 두 금융기관에 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 보험사 연금상품의 세제적격 여부 판별 기준 • 보험사에서 미래에셋증권으로의 이전 가능 상품 범위 • 현재 수관 절차와 제한 **금지 주장** • 세제적격 보험상품은 모두 미래에셋증권으로 이전 가능 • 상품명에 연금저축 또는 개인연금이 들어가면 이전 가능

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 보험 연금상품의 세제 구분과 수관 가능 여부를 문서 근거 없이 단정하지 않음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 23. 미래에셋 MA-PP-004 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-004` 검색
- 질문: [개인연금] 연금저축계좌에 상품에 투자를 하지 않은 예수금(현금)은 어떻게 운용되나요?

**목표 답변**

> 제공 문서에는 연금저축계좌의 미투자 예수금이 예탁금 이용료 대상인지, 적용 이용료율·금액 구간·지급일이 무엇인지 나와 있지 않습니다. 먼저 해당 잔액이 예탁금 이용료 대상인지 확인하고, 대상이라면 미래에셋증권의 최신 예탁금 이용료 공시에서 계좌 유형과 잔액 구간을 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 연금저축계좌 예수금의 운용 방식 • 현재 예탁금 이용료율과 잔액 구간 • 예탁금 이용료 지급 주기와 지급일 **금지 주장** • 100만원 이하에 연 2% 또는 연 2.25% 적용 • 100만원 초과에 연 0.60% 적용 • 분기 시작월 둘째 주 마지막 영업일 지급

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 연금저축계좌 미투자 예수금의 이용료 대상 여부와 적용 기준을 제공 문서로 확인할 수 없다고 제한하고 있음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 24. 미래에셋 MA-PP-005 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-005` 검색
- 질문: [개인연금] 연금해지신청 후 전화를 받아야된다고 하는데 지금 해외라 다른 인증할수있는 방법이 있나요?

**목표 답변**

> 제공 문서에서는 온라인 연금해지 신청 뒤 필요한 본인확인 방식과 해외 체류 고객에게 허용되는 대체 인증수단을 확인할 수 없습니다. 유선통화만 가능하다고 단정하지 말고, 미래에셋증권의 공식 상담 채널을 통해 해외 연락 가능 번호와 대체 절차가 있는지 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 온라인 해지 신청 후 본인확인 절차 • 해외 체류 중 가능한 대체 인증수단 • 해외 연락 가능 번호 등록 및 처리 방식 **금지 주장** • 계좌 인증은 유선통화로만 가능 • 다른 인증방법은 전혀 불가능

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 해외 체류 고객의 대체 인증수단을 문서 근거 없이 단정하지 않고 공식 상담 채널 확인으로 제한하고 있음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 25. 미래에셋 MA-PP-008 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-008` 검색
- 질문: [개인연금] ’세금우대 약정정보가 없습니다‘라는 메시지가 나옵니다.

**목표 답변**

> 제공 문서에는 “세금우대 약정정보가 없습니다” 메시지의 발생 조건과 해결 절차가 없습니다. 이전용 계좌 또는 해지 계좌 때문이라고 단정하지 말고, 해당 계좌의 개설 목적·이전 완료 여부·해지 상태를 확인한 뒤 미래에셋증권에 오류코드 기준으로 문의해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 오류 메시지의 정확한 발생 조건 • 이전용 계좌의 한도 등록 시점 • 신규 계좌 재개설이 필요한 조건 **금지 주장** • 이 메시지는 반드시 이전용 계좌에서 발생 • 타사 이전 완료 후에는 항상 한도 등록 가능 • 신규 연금저축계좌를 다시 개설하면 해결

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - `세금우대 약정정보가 없습니다` 메시지의 발생 조건과 해결 절차를 문서 근거 없이 추정하지 않음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 26. 미래에셋 MA-PP-009 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-009` 검색
- 질문: [개인연금] 주식계좌에 있는 일부 주식을 연금계좌로 옮기고 싶은데 가능한가요?

**목표 답변**

> 제공 문서에는 일반 주식계좌의 주식이나 ETF를 연금저축계좌로 직접 입고할 수 있는지에 대한 규정이 없습니다. 현금만 입금 가능하다고 단정할 수 없으므로, 일반계좌에서 연금계좌로의 현물 이전 가능 여부를 상품 종류와 계좌 유형별로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 일반계좌 보유 주식·ETF의 연금저축계좌 직접 입고 가능 여부 • 현금 납입만 허용되는지 여부 **금지 주장** • 일반주식과 ETF는 연금저축계좌로 직접 입고 불가 • 연금저축계좌에는 현금으로만 입금 가능

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 일반 주식계좌 보유 주식의 연금계좌 현물 이전 가능 여부를 문서 근거 없이 가능/불가로 단정하지 않음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 27. 미래에셋 MA-PP-010 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-010` 검색
- 질문: [개인연금] 연금저축계좌가 여러개 있는데 나중에 연금개시를 할 때 통합해서 개시할 수있나요?

**목표 답변**

> 제공 문서에는 미래에셋증권에 보유한 여러 연금저축계좌를 하나로 합쳐 연금개시할 수 있는지, 가입일이 2013년 3월 전후인 계좌 사이의 합산 방향과 보유상품 이전 방식이 제시되어 있지 않습니다. 계좌별 최초 가입일·개시 여부·보유상품을 기준으로 통합 가능 여부를 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 동일 금융회사 내 연금저축계좌 통합 가능 여부 • 2013년 3월 전후 계좌의 이전 허용 방향 • 보유상품을 매도하지 않고 이전할 수 있는 조건 **금지 주장** • 2013년 3월 이전 계좌를 이후 계좌로만 합칠 수 있음 • 당사 내 이전은 상품 잔고 그대로 항상 가능 • 온라인·모바일 접수 후 유선 확인으로 처리

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 28. 미래에셋 MA-PP-012 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-012` 검색
- 질문: [개인연금] 연금을 이전한 경우 타사 계좌에서 추가로 발생하는 분배금, 배당 등은 어떻게 처리되나요?

**목표 답변**

> 제공 문서에는 연금계좌 이전 뒤 이전한 금융회사에 추가로 들어오는 분배금·배당·이자를 어느 계좌로 지급하는지, 권리 발생 중인 계좌의 이전 가능 여부가 없습니다. 추가 지급금의 처리 주체와 지급 계좌는 이전 전 금융회사와 이전받은 금융회사에 각각 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 권리 발생 중인 연금저축계좌의 이전 가능 여부 • 이전 후 발생한 분배금·배당·이자의 귀속 계좌 • 금융회사별 후속 지급 처리 절차 **금지 주장** • 권리가 있는 계좌는 미래에셋증권에서 이전 불가 • 분배금·이자는 반드시 이전한 회사가 처리

**사람 검수 결과**

- 판정: [x] OK  [ ] 수정 필요  [ ] 보류
- 확인:
  - [x] 질문 의도
  - [x] 목표 답변
  - [x] 필수 주장
  - [x] 부족 근거·금지 주장
- 수정 메모:
  - 현재 `미지원` 유지가 적절함.
  - 연금계좌 이전 후 추가 분배금·배당 처리 주체와 지급 계좌를 문서 근거 없이 단정하지 않음.
- 최종 반영 여부: [ ] 반영 완료  [x] 반영 불필요  [ ] 미반영

### 29. 미래에셋 MA-PP-013 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-013` 검색
- 질문: [개인연금] 보유중인 계좌가 개인연금 또는 IRP계좌인지 확인할 수 있는방법이있나요?

**목표 답변**

> 제공 문서에는 M-STOCK이나 홈페이지에서 계좌가 연금저축인지 개인형 IRP인지 확인하는 화면 경로와 표시 문구가 없습니다. 계좌확인서·가입확인서 발급 메뉴나 계좌명 표시는 문서만으로 안내할 수 없으므로 현재 앱의 계좌 상세정보 또는 공식 상담 채널에서 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 계좌확인서·가입확인서 발급 경로 • 연금계좌현황 화면의 계좌 유형 표시 문구 **금지 주장** • 특정 M-STOCK 메뉴 경로를 제시 • 계좌번호 뒤에 연금저축계좌(신) 또는 퇴직연금_개인형IRP가 표시된다고 단정

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 30. 미래에셋 MA-PP-015 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-015` 검색
- 질문: [개인연금] 연금저축계좌를 조회를 해보니 만기일이있던데 어떤 의미 인가요?

**목표 답변**

> 제공 문서에는 연금저축계좌의 적립만기일이 무엇을 뜻하는지, 만기 후 입금 가능 여부와 연장 절차가 없습니다. 적립만기일이 계약 종료를 뜻하지 않는다거나 언제든 연장할 수 있다고 단정할 수 없으므로, 계좌 상세의 만기 구분과 현재 변경 가능 여부를 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 적립만기일의 법적·업무상 의미 • 만기 경과 후 연장 가능 여부 • M-STOCK·홈페이지 변경 경로 **금지 주장** • 적립만기일은 추가 입금 가능 여부만 의미 • 적립만기일은 계약 종료가 아님 • 경과 후에도 언제든 연장 가능

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 31. 미래에셋 MA-PP-023 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-023` 검색
- 질문: [개인연금] 연금계좌에서 연금 수령 방법은 어떻게 되나요?

**목표 답변**

> 제공 문서에는 미래에셋증권 연금저축계좌에서 선택할 수 있는 연금 수령 방식의 명칭과 각 방식의 계산 기준이 없습니다. 한도분할식·정액식·기간분할식·임의식 등 구체적인 방식을 문서 근거 없이 열거할 수 없으므로, 현재 계좌에서 제공되는 수령 방식과 변경 가능 여부를 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 연금저축계좌의 수령 방식 종류 • 각 수령 방식의 금액·기간 결정 방식 • 수령 방식 변경 가능 여부 **금지 주장** • 한도분할식·정액식·기간분할식·임의식 네 가지가 제공됨 • 각 방식의 구체적 정의를 단정

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 32. 미래에셋 MA-PP-029 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-029` 검색
- 질문: [개인연금] 타사에서 이미 개시한 연금계좌를 미래에셋증권으로 이전할 수 있나요?

**목표 답변**

> 제공 문서에는 타사에서 이미 연금개시한 연금저축·IRP를 미래에셋증권이 현재 수관할 수 있는지, 이전용 계좌와 지급 중단 후 재신청 절차, 계약 특성별 제한이 제시되어 있지 않습니다. 따라서 개시된 계좌도 이전 가능하다고 단정할 수 없으며, 출발 금융사와 미래에셋증권에 계좌 종류·개시 상태·보유상품 기준으로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 개시된 연금계좌의 미래에셋증권 수관 가능 여부 • 연금저축과 IRP별 수관용 계좌 요건 • 수관 시 기존 지급 방식의 유지·중단 여부 • 계약 특성·시스템 차이에 따른 제한 **금지 주장** • 연금개시된 계좌도 미래에셋증권으로 이전 가능 • 연금저축은 이전용 계좌로만 수관 가능 • IRP는 무잔고 신규 계좌로 수관해야 함 • 수관하면 기존 연금지급 방식이 중단되고 별도 신청 필요

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 33. 미래에셋 MA-PP-031 · 미지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-031` 검색
- 질문: [개인연금] 보험사의 연금저축보험을 수관하려 하니, 해약환급금이 적은데 왜 그런거죠?

**목표 답변**

> 제공 문서에는 연금저축보험의 해약환급금이 원금보다 적어지는 이유, 사업비 공제 구조, 계약이전 시 세금 처리에 관한 직접 근거가 없습니다. 답변하려면 보험사가 산출한 계약이전 예정금액과 해약환급금의 차이, 사업비·수수료·세금 공제 내역이 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 연금저축보험의 초기 사업비 구조와 원금 도달 기간 • 계약이전 시 미차감 사업비 징수 여부 • 보험사가 안내한 금액의 세전·세후 구분과 세금 처리 **금지 주장** • 5~7년이 지나야 원금에 도달한다고 단정하는 주장 • 계약이전에는 세금이 전혀 없다고 단정하는 주장 • 안내금액에 기타소득세 16.5%가 포함되었다고 추정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 34. 미래에셋 MA-RP-004 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-004` 검색
- 질문: [퇴직연금] 퇴직연금IRP계좌에 '거래제한-퇴직전 출금고 거래제한'이라고 되어 있는데 왜 그런가요?

**목표 답변**

> 제공 문서에는 미래에셋증권의 '거래제한-퇴직전 출금고 거래제한' 코드가 부여되는 정확한 사유, 제한되는 업무 범위와 해제 조건을 직접 확인할 근거가 없습니다. 따라서 이 표시가 법정 중도인출 제한 때문에 생겼다거나 매매·조회에는 영향이 없다고 단정할 수 없습니다. 현재 계좌의 계약상태와 제한 대상 업무를 현행 시스템 기준으로 별도 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 해당 거래제한 코드의 정확한 부여 사유 • 출금·입고·매매·조회 중 실제 제한되는 업무 • 해지·연금지급 또는 계약상태 변경 시 해제 조건 **금지 주장** • 해당 코드가 법정 중도인출 제한 때문에 부여됐다고 단정하는 주장 • 해당 제한이 매매와 조회에는 영향을 주지 않는다는 주장 • 해지나 연금지급 때 자동으로 해제된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 35. 미래에셋 MA-RP-007 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-007` 검색
- 질문: [퇴직연금] 타사 연금보험을 미래에셋증권 IRP계좌로 이전 신청 했는데 손실 없이 그대로 이전되나요?

**목표 답변**

> 질문의 '연금보험'이 세제적격 연금저축보험인지 일반 연금보험인지 제공 자료만으로는 알 수 없습니다. 제공 문서에는 어느 유형의 보험을 IRP로 이전할 수 있는지, 이전 시 세금과 보험사의 사업비·수수료, 실제 이전금액을 뒷받침하는 직접 근거가 없습니다. 따라서 손실 없이 그대로 이전된다고 보장할 수 없으며, 정확한 상품 유형과 보험사의 계약이전 예상금액·공제 항목, 수관 가능한 계좌 유형을 추가로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 질문의 연금보험이 연금저축보험인지 일반 연금보험인지 • 보험에서 IRP로의 이전 가능 계좌 유형과 요건 • 계약이전 시 세금 추징 여부 • 보험사 사업비·수수료와 실제 이전금액 **금지 주장** • 질문의 연금보험이 연금저축보험이라고 단정하는 주장 • 특정 연령·계약기간 요건이면 항상 IRP로 이전 가능하다는 주장 • 세금이나 비용 없이 전액 이전된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 36. 미래에셋 MA-RP-010 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-010` 검색
- 질문: [퇴직연금] IRP개설시 증빙서류 중 건강보험자격득실확인서는 모바일제출이 가능하던데 진행이 안됩니다.

**목표 답변**

> 제공 자료에는 IRP 개설 중 건강보험자격득실확인서의 모바일 제출 연동 조건, 사용할 수 있는 인증서, 지역가입자 제한과 팩스 제출 절차를 직접 뒷받침하는 근거가 없습니다. 모바일 제출이 되지 않는 원인을 단정할 수 없으므로, 인증서 등록 상태·건강보험 가입자 구분·개설 단계와 현재 대체 제출 채널을 확인할 자료가 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 모바일 제출에 필요한 인증서 종류 • 건강보험 지역가입자의 서류 인정 여부 • 비대면 개설 중 대체 제출 채널과 팩스번호 **금지 주장** • 증권용 또는 범용 인증서가 있으면 반드시 자동 제출된다는 주장 • 지역가입자는 해당 서류를 사용할 수 없다는 주장 • 특정 팩스번호로 보내면 된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 37. 미래에셋 MA-RP-012 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-012` 검색
- 질문: [퇴직연금] 퇴직연금에 현재 보유한 예금상품 만기나 금리를 알 수 있나요?

**목표 답변**

> 제공 문서에는 퇴직연금 계좌의 예금별 만기일·적용금리를 조회하는 기능이나 M-STOCK·홈페이지 경로를 직접 뒷받침하는 근거가 없습니다. 답변하려면 현재 계좌의 예금 명세와 현행 조회 화면 안내가 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 예금 명세별 만기일과 적용금리 조회 가능 여부 • M-STOCK과 홈페이지의 조회 범위 차이 • 현재 조회 메뉴 경로 **금지 주장** • M-STOCK에서 예금별 만기와 금리를 모두 볼 수 있다는 주장 • 홈페이지에서는 만기만 볼 수 있다는 주장 • 특정 메뉴 경로가 현재 유효하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 38. 미래에셋 MA-RP-013 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-013` 검색
- 질문: [퇴직연금] 퇴직연금/IRP계좌에서 ETF 매매체결시 SMS 알림받는 방법 알려주세요.

**목표 답변**

> 제공 문서에는 퇴직연금·IRP ETF 체결내역의 SMS 통지처 등록 방법, 실시간 또는 일간 통지 방식과 발송 시점을 직접 뒷받침하는 근거가 없습니다. 현재 알림 서비스의 제공 여부와 등록 화면을 확인할 자료가 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • ETF 체결 SMS 알림 등록 경로 • 실시간·일간 통지 방식 • 장 종료 후 발송 여부 **금지 주장** • 퇴직연금 알리미에서 SMS를 선택하면 된다는 주장 • 실시간이 아니라 장 종료 후 하루 한 번 발송된다는 주장 • 현재 특정 M-STOCK 메뉴가 유효하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 39. 미래에셋 MA-RP-014 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-014` 검색
- 질문: [퇴직연금] 퇴직연금/IRP계좌에 ELB 신청하려고 하는데 어떻게 하나요?

**목표 답변**

> 제공 문서에는 퇴직연금·IRP 계좌의 ELB 발행 주기, 사전예약 기간, 청약 자격과 관리점 신청 절차를 직접 뒷받침하는 근거가 없습니다. 현재 청약 가능한 ELB가 있는지와 계좌별 예약·청약 절차를 확인할 자료가 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • ELB의 현재 발행 일정과 판매 여부 • 예약 접수 기간과 한도 • 퇴직연금·IRP 관리점 신청 절차 **금지 주장** • ELB가 매주 금요일 발행된다는 주장 • 월요일부터 유선예약을 받는다는 주장 • 예약한 계좌만 청약 가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 40. 미래에셋 MA-RP-015 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-015` 검색
- 질문: [퇴직연금] 퇴직연금/IRP계좌에서 ETF 예약 주문 할 수 있나요?

**목표 답변**

> 제공 문서에는 퇴직연금·IRP의 ETF 예약주문 허용 여부와 주문 가능 시간대를 직접 뒷받침하는 근거가 없습니다. 따라서 예약주문이 불가능하고 정규장 주문만 가능하다고 단정할 수 없으며, 현재 주문 화면과 계좌별 거래 기준을 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 퇴직연금·IRP ETF 예약주문 허용 여부 • 정규장 외 주문 가능 여부 • 현행 주문 채널과 시간 **금지 주장** • ETF 예약주문은 항상 불가능하다는 주장 • 정규장 주문만 가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 41. 미래에셋 MA-RP-016 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-016` 검색
- 질문: [퇴직연금] 사용중지했던 퇴직연금 IRP계좌를 다시 사용 할 수 있나요?

**목표 답변**

> 제공 문서에는 해지 지급된 IRP나 타사 이전으로 이관해지된 IRP의 재사용 가능 여부를 직접 뒷받침하는 근거가 없습니다. 계좌의 현재 계약상태와 재활성화 가능 여부를 확인할 자료가 추가로 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 해지 지급 계좌의 재사용 가능 여부 • 타사 이전으로 종료된 계좌의 재사용 가능 여부 • 신규개설 필요성 **금지 주장** • 해지된 IRP는 어떤 경우에도 재사용할 수 없다는 주장 • 항상 신규 IRP를 개설해야 한다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 42. 미래에셋 MA-RP-018 · 미지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-018` 검색
- 질문: [퇴직연금] 은행에 예금을 갖고 있는데 IRP에 동일한 은행상품을 가입하면 예금자보호는 어떻게 되나요?

**목표 답변**

> 제공 자료에는 일반 은행예금과 같은 은행의 IRP 예금에 예금자보호 한도가 별도로 적용되는지 또는 합산되는지, DC와 IRP 사이에는 어떻게 적용되는지를 직접 뒷받침하는 근거가 없습니다. 은행·저축은행 등 금융회사 유형별 기준도 이 질문에 답할 수 있는 범위로 확인되지 않으므로, 해당 금융회사의 유형과 IRP 상품의 보호 대상 여부, 현행 합산 기준을 별도로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거·주의점**

- 직접 인용할 제공 문서 근거 없음

**부족 근거·금지 주장**

- *부족 근거** • 일반예금과 퇴직연금 예금의 보호한도 분리·합산 여부 • DC와 IRP 간 합산 기준 • 은행·저축은행 등 금융회사 유형별 적용 기준 • 해당 IRP 상품의 예금자보호 대상 여부 **금지 주장** • 일반계좌와 별도로 무조건 1억원까지 보호된다는 주장 • DC와 IRP를 모두 합해 정확히 1억원이라는 주장 • 실물이전 불가사유표의 한도 점검을 일반 예금자보호 합산 규칙으로 단정하는 주장 • 모든 퇴직연금 상품이 예금자보호 대상이라는 주장 **검토 메모** • 별도 보호한도 문구는 retrieval OCR에서만 확인되고 최종 인용 가능한 Docling item text가 없어 제외함.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

## 4차: 미래에셋 부분 지원 36개 (36개)

### 43. 미래에셋 MA-PP-001 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-001` 검색
- 질문: [개인연금] 개인연금계좌에 입금이 안되는데 어떻게 해야 하죠?

**목표 답변**

> 제공 문서에서 확인되는 우선 점검 항목은 연간 납입한도입니다. 연금저축과 DC/IRP의 납입한도는 전 금융기관에 설정된 금액을 합산해 연 1,800만원까지입니다. 먼저 전 금융기관의 합산 납입한도 설정액을 확인하세요. 다만 적립만기일, 미사용한도 조회·변경 경로, 그 밖의 입금 오류 사유는 문서에서 확인되지 않으므로 계좌 상태와 오류 메시지를 기준으로 미래에셋증권에 확인해야 합니다.

**필수 주장**

- *MA-PP-001-C1** 연금저축과 DC/IRP의 납입한도는 전 금융기관 합산 연 1,800만원이다. 근거: E-DOC6-T45-F122B6BA1E5EC441, E-DOC6-T46-42FD7D62E901C0FE

**문서 근거·주의점**

- *E-DOC6-T45-F122B6BA1E5EC441** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/45` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “연금저축과 DC/IRP 합산하여 연간 1,800만원까지 한도 설정 가능” **E-DOC6-T46-42FD7D62E901C0FE** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/46` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “전 금융기관 합산 적용”

**부족 근거·금지 주장**

- *부족 근거** • 적립만기일의 의미와 연장 가능 여부 • 미래에셋증권의 한도 조회·변경 화면 경로 • 해당 계좌의 실제 입금 실패 원인 **금지 주장** • 입금 실패 원인이 적립만기일 경과라고 단정 • 특정 M-STOCK·홈페이지 경로를 제시 • 미사용한도가 0원이면 다른 계좌 한도를 감액하면 된다고 단정 **검토 메모** • 입금 실패 원인 가운데 연간 통합 납입한도만 직접 근거가 있음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 44. 미래에셋 MA-PP-014 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-014` 검색
- 질문: [개인연금] 연금저축계좌를 해지했는데 세금이 나왔습니다. 세액공제는 못받았는데 어떻게 해야 하나요?

**목표 답변**

> 세액공제를 받지 않은 원금은 인출할 때 비과세가 원칙입니다. 따라서 실제 해지세금이 원천징수됐다면 해당 납입금이 계좌에서 세액공제 미적용 재원으로 반영됐는지 확인해야 합니다. 다만 이미 원천징수된 세금의 재원변경·환급 절차, 필요한 확인서와 방문 시간은 제공 문서에 없어 단정할 수 없습니다.

**필수 주장**

- *MA-PP-014-C1** 세액공제를 받지 않은 납입금은 인출할 때 비과세다. 근거: E-DOC39-T16-9B2148340A202D83

**문서 근거·주의점**

- *E-DOC39-T16-9B2148340A202D83** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/16` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0002` 인용: “세액공제를 받지 않은 납입금(ISA전환금 포함)이 있을 경우 인출할 때에도 전액 비과세이며, 연금수령한도 초과분에 대해서도 과세되지 않는다.”

**부족 근거·금지 주장**

- *부족 근거** • 과세재원 정정·환급 신청 절차 • 연금보험료 등 소득·세액공제 확인서의 필요 여부 • 처리 가능한 채널과 영업시간 **금지 주장** • 7월 이후에만 전년도 세액공제 적용 여부 확인 가능 • 특정 확인서를 발급해 영업점에 방문해야만 처리 가능 • 업무시간을 평일 08:30~16:00으로 단정 **검토 메모** • 비과세 원칙은 직접 근거가 있으나 사후 정정 절차는 근거 없음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 45. 미래에셋 MA-PP-016 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-016` 검색
- 질문: [개인연금] 연금저축계좌에서 공모주 청약이나 주식거래가 가능한가요?

**목표 답변**

> 제공 문서는 연금계좌 안에서 국내주식형·해외주식형 등 ETF에 투자할 수 있음을 전제로 설명합니다. 다만 연금저축계좌에서 공모주 청약, 일반주식·해외주식·예금·채권 거래가 가능한지와 허용 ETF 범위는 직접 제시하지 않으므로, 해당 거래의 가능·불가를 문서만으로 확정할 수 없습니다.

**필수 주장**

- *MA-PP-016-C1** 연금계좌에서 ETF에 투자할 수 있다. 근거: E-DOC43-T20-3ED622EE7806CCBB

**문서 근거·주의점**

- *E-DOC43-T20-3ED622EE7806CCBB** — [doc43.docx](https://docs.google.com/document/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc43` · `#/texts/20` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112` retrieval `knowledge-f146981691bb-0002` 인용: “연금계좌에서 국내주식형 월배당 ETF를 투자하면 분배금에 대해 과세가 이연된다. 해외주식형 월배당 ETF와 그 밖의 ETF의 경우 매매차익과 분배금 모두 과세가 이연된다.”

**부족 근거·금지 주장**

- *부족 근거** • 연금저축계좌의 공모주 청약 가능 여부 • 일반주식·해외주식·예금·장내외채권 거래 가능 여부 • 허용 ETF와 금지 ETF의 정확한 범위 **금지 주장** • 공모주 청약은 불가능 • 일반주식·해외주식·예금·채권은 모두 거래 불가 • 레버리지·인버스를 제외한 모든 국내 상장 ETF와 리츠·인프라 거래 가능 **검토 메모** • ETF 투자 일반만 직접 근거가 있고 질문의 공모주·주식 거래 여부는 근거 없음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 46. 미래에셋 MA-PP-017 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-017` 검색
- 질문: [개인연금] ISA 만기 해지 후 연금저축계좌와 IRP계좌에 각각 나눠서 전환입금이 가능한가요?

**목표 답변**

> 문서에는 의무가입기간 3년을 거친 ISA 만기자금을 60일 안에 연금저축 또는 IRP로 이전할 수 있고, 같은 기간 여러 차례 나눠 입금할 수 있다고 되어 있습니다. 다만 한 건의 ISA 만기자금을 연금저축과 IRP 두 계좌에 각각 배분할 수 있다는 명시는 없어, 두 계좌 분할 가능 여부는 신청 전에 확인해야 합니다.

**필수 주장**

- *MA-PP-017-C1** 의무가입기간 3년을 충족한 ISA 만기자금은 60일 안에 연금저축 또는 IRP로 이전할 수 있다. 근거: E-DOC23-T3-D558B1E481AB051A, E-DOC23-T3-941535FC97BA0C52 **MA-PP-017-C2** ISA 만기자금은 60일 안에 여러 차례 나눠 전환입금할 수 있다. 근거: E-DOC33-T65-37102BE7A2310893

**문서 근거·주의점**

- *E-DOC23-T3-D558B1E481AB051A** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “의무가입기간 3년이 지나서 해지하면 만기해지로 인정되서 비과세 · 분리과세 세제혜택을 받을 수 있다.” **E-DOC23-T3-941535FC97BA0C52** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “이렇게 세제혜택을 받은 ISA만기자금은 60일 내에 연금계좌(연금저축, IRP)로 옮길 수 있다.” **E-DOC33-T65-37102BE7A2310893** — [doc33.pptx](https://docs.google.com/presentation/d/1gF7eKVvP9VNjqDvQo4Z_n6lgmmFqCEO-/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc33` · `#/texts/65` · label `list_item` · variant `delivery` page/slide `5`; charspan `0:43`; bbox `{"b":1643154.0,"coord_origin":"BOTTOMLEFT","l":954821.0,"r":9290760.0,"t":2104819.0}` retrieval `knowledge-0aba02f48732-0001` 인용: “가능합니다. ISA 만기 해지된 금액 내에서 60일 이내 횟수 제한 없습니다.”

**부족 근거·금지 주장**

- *부족 근거** • 한 ISA 만기자금을 연금저축과 IRP에 동시에 배분할 수 있는지 여부 **금지 주장** • 연금저축과 IRP에 나눠 전환입금할 수 있다고 단정 • 두 계좌로 나누면 추가 세액공제 한도가 각각 300만원씩 생김 **검토 메모** • 복수 회차 입금은 직접 근거가 있으나 서로 다른 두 종류 계좌로의 배분은 명시되지 않음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 47. 미래에셋 MA-PP-018 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-018` 검색
- 질문: [개인연금] 현재 연금저축계좌1개 이용중인데, 추가로 연금저축계좌 개설 가능한가요?

**목표 답변**

> 제공 문서는 이미 연금개시된 계좌에는 개인납입금을 추가로 넣을 수 없어, 세액공제를 위한 개인납입이 필요하면 새 연금계좌를 개설해야 한다고 설명합니다. 따라서 이 문서의 개시 계좌 문맥에서는 추가 개설이 가능하다고 볼 수 있습니다. 다만 아직 개시하지 않은 연금저축계좌를 보유한 일반적인 경우의 추가 개설 조건이나 계좌 수 상한은 문서에 명시되어 있지 않습니다. 납입한도는 연금저축과 DC/IRP를 전 금융기관 합산해 연 1,800만원까지 관리합니다.

**필수 주장**

- *MA-PP-018-C1** 이미 연금개시된 계좌에는 개인납입금을 추가로 넣을 수 없고, 개인납입이 필요하면 새 연금계좌를 개설해야 한다. 근거: E-DOC40-T23-AB7E6F6927036EF2 **MA-PP-018-C2** 납입한도는 연금저축과 DC/IRP를 전 금융기관 합산해 연 1,800만원까지 관리한다. 근거: E-DOC6-T45-F122B6BA1E5EC441, E-DOC6-T46-42FD7D62E901C0FE

**문서 근거·주의점**

- *E-DOC40-T23-AB7E6F6927036EF2** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/23` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0004` 인용: “개시된 계좌로는 퇴직금에 한해 입금이 가능하고, 개인납입금을 추가 불입할 수 없다. 세액공제를 위한 개인 납입이 필요하다면 새로운 연금계좌를 개설해야 한다.” **E-DOC6-T45-F122B6BA1E5EC441** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/45` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “연금저축과 DC/IRP 합산하여 연간 1,800만원까지 한도 설정 가능” **E-DOC6-T46-42FD7D62E901C0FE** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/46` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “전 금융기관 합산 적용”

**부족 근거·금지 주장**

- *부족 근거** • 연금개시 전 일반 연금저축 보유자의 추가 개설 조건 • 연금저축계좌 개수의 절대 상한 **금지 주장** • 모든 기존 연금저축 보유자가 제한 없이 추가 개설할 수 있다고 일반화 • 개수 제한 없이 무제한으로 개설 가능 **검토 메모** • 추가 개설 근거는 이미 연금개시된 계좌와 새 개인납입 계좌를 병행하는 문맥에 한정됨.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 48. 미래에셋 MA-PP-019 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-019` 검색
- 질문: [개인연금] 연금저축계좌에서 연금개시를 할때 모든 보유 상품을 매도해야하나요?

**목표 답변**

> 제공 문서만으로 연금개시 때 보유상품을 전량 매도해야 하는지는 확정할 수 없습니다. 다만 연금개시 후 초기에 최소 금액만 수령하고 나머지 자금은 계좌 안에서 계속 운용할 수 있다는 점은 확인됩니다. 상품별로 매도 없이 연금개시가 되는지, 지급 재원을 마련하기 위해 언제 어떤 상품을 현금화해야 하는지는 미래에셋증권의 지급 절차를 별도로 확인해야 합니다.

**필수 주장**

- *MA-PP-019-C1** 연금개시 후 일부만 수령하고 나머지 자금은 연금계좌 안에서 계속 운용할 수 있다. 근거: E-DOC40-T16-C51138A787595399

**문서 근거·주의점**

- *E-DOC40-T16-C51138A787595399** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/16` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0003` 인용: “연금 개시를 신청하되 초반 10년은 최소 금액만 연금으로 수령해 실수령연차를 쌓고, 나머지 자금은 연금계좌 안에서 과세이연 상태로 운용하라.”

**부족 근거·금지 주장**

- *부족 근거** • 연금개시 자체에 보유상품 전량 매도가 필요한지 여부 • 펀드 지급매도의 자동 처리 방식 • ETF·리츠·인프라의 직접매도 필요 여부와 시점 **금지 주장** • 연금개시 때 모든 보유상품을 매도할 필요가 없다고 단정 • 펀드는 정해진 순서 또는 보유비율대로 자동 매도 • ETF·리츠·인프라는 지급일 3영업일 전에 직접 매도해야 함 **검토 메모** • 잔여 자금의 계좌 내 계속 운용은 직접 근거가 있으나, 상품 보유 상태와 지급매도 절차는 근거가 없음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 49. 미래에셋 MA-PP-020 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-020` 검색
- 질문: [개인연금] 연금 개시 후에도 펀드교체가 가능한가요?

**목표 답변**

> 제공 문서는 연금개시 후에도 남은 자금을 연금계좌 안에서 계속 운용할 수 있음을 설명하므로, 개시 자체가 운용을 종료시키는 것은 아닙니다. 다만 미래에셋증권에서 개시 후 펀드 교체 주문이 가능한 범위, 지급일 직전 매매 시 처리와 오류 알림 절차는 직접 확인되지 않습니다.

**필수 주장**

- *MA-PP-020-C1** 연금개시 후에도 남은 자금을 연금계좌 안에서 계속 운용할 수 있다. 근거: E-DOC40-T16-9289FB2384061860

**문서 근거·주의점**

- *E-DOC40-T16-9289FB2384061860** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/16` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0003` 인용: “나머지 자금은 연금계좌 안에서 과세이연 상태로 운용하라.”

**부족 근거·금지 주장**

- *부족 근거** • 연금개시 후 펀드 교체 주문의 허용 범위 • 지급일 직전 상품 변경 시 지급매도 처리 • ETF·리츠·인프라의 지급재원 마련 절차와 오류 알림 **금지 주장** • 연금개시 후 모든 상품의 교체매매가 항상 가능 • 교체매매 후 관리점에 통화하면 지급 차질이 없음 • 지급 오류 시 반드시 알림톡 또는 SMS 발송 **검토 메모** • 개시 후 계속 운용은 직접 근거가 있으나 펀드 교체매매의 구체적 허용은 명시되지 않음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 50. 미래에셋 MA-PP-021 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-021` 검색
- 질문: [개인연금] 2001년 이전 가입할 수 있던 구개인연금저축에 대해 알고 싶어요.

**목표 답변**

> (구)개인연금저축은 현재 연금저축계좌와 달리 납입액의 40%를 소득공제하며 공제 한도는 연 72만원입니다. 문서에는 분기 300만원, 연 1,200만원까지 납입할 수 있고, 가입기간 10년 이상이면서 만 55세 이후에 최소 5년 이상 나눠 받으면 운용수익이 비과세라고 설명되어 있습니다. 다만 가입 가능 기간과 현재 신규가입·수관 가능 여부는 스냅샷에서 확인되지 않습니다.

**필수 주장**

- *MA-PP-021-C1** (구)개인연금저축은 납입액의 40%를 연 72만원 한도로 소득공제하며 분기 300만원, 연 1,200만원까지 납입할 수 있다. 근거: E-DOC25-T9-0D1EC29FC0D7952B **MA-PP-021-C2** (구)개인연금저축은 가입기간 10년 이상이고 만 55세 이후 최소 5년 이상 나눠 받아야 운용수익 비과세 요건을 충족한다. 근거: E-DOC25-TB0-F01F75840C96C73D, E-DOC25-T10-76140F64FAECEE9F

**문서 근거·주의점**

- *E-DOC25-T9-0D1EC29FC0D7952B** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/texts/9` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` retrieval `knowledge-5914e8bedc6b-0000` 인용: “매년 납입액의 40%를 소득공제 받을 수 있는데 소득공제 한도는 연 72만원이다. 소득공제 한도까지 채우려면 매년 180만원씩 납입하면 된다. 여유가 된다면 분기당 300만원, 연1,200만원까지 납입이 가능하니” **E-DOC25-TB0-F01F75840C96C73D** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/tables/0` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` table cells `r2c1` retrieval `knowledge-5914e8bedc6b-0002` 인용: “가입기간 10년 이상 & 만 55세 이후” **E-DOC25-T10-76140F64FAECEE9F** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/texts/10` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` retrieval `knowledge-5914e8bedc6b-0000` 인용: “55세이상이면 연금개시가 가능하고 5년 이상에 걸쳐 나누어 받아야 한다는 조건을 지켜야 한다. 그래야 늘어난 수익에 대해 비과세 혜택을 받을 수 있다.”

**부족 근거·금지 주장**

- *부족 근거** • 가입 가능 기간 • 현재 신규가입 가능 여부 • 기존 계좌의 수관 목적 신규개설 가능 여부 **금지 주장** • 1994년 6월부터 2000년 12월 31일까지만 가입 가능 • 2001년 이후 판매가 중단되어 현재 신규가입 불가 • 현재 신규개설은 기존 계좌 수관 목적으로만 가능 **검토 메모** • 상품 특징은 직접 근거가 있으나 역사적 판매기간과 현재 판매·수관 상태는 없음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 51. 미래에셋 MA-PP-022 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-022` 검색
- 질문: [개인연금] 연금계좌에서 연금을 수령하다가 중단할 수도 있나요?

**목표 답변**

> 연금 지급을 중단하는 상황은 문서에 포함되어 있고, 중단한 해에는 연금실제수령연차가 쌓이지 않습니다. 재개 가능성은 (구)개인연금저축 문서에서는 확인되지만, 현재 미래에셋증권 연금저축·IRP에서 중단·재개를 신청하는 방법과 지급계좌·금액·주기 변경 범위는 직접 근거가 없습니다. 따라서 현재 계좌의 중단·재개 가능 여부와 절차는 확인이 필요합니다.

**필수 주장**

- *MA-PP-022-C1** 연금 인출을 중단한 해에는 연금실제수령연차가 누적되지 않는다. 근거: E-DOC40-T13-1F5DCAE0B87FDB2E **MA-PP-022-C2** (구)개인연금저축은 첫 수령 후 중단했다가 다시 시작할 수 있다. 근거: E-DOC25-T11-7CE194647A0C67DD

**문서 근거·주의점**

- *E-DOC40-T13-1F5DCAE0B87FDB2E** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/13` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0002` 인용: “인출을 중단한다면 연금실제수령연차도 누적되지 않는다.” **E-DOC25-T11-7CE194647A0C67DD** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` retrieval `knowledge-5914e8bedc6b-0001` 인용: “60세에 처음 연금을 수령하고 바로 중단했다 하더라도 언제든 재개시가 가능하고”

**부족 근거·금지 주장**

- *부족 근거** • 현재 연금저축·IRP의 지급중단·재개 가능 여부와 신청 경로 • 지급계좌·방법·금액·주기·매도순서 변경 가능 범위 **금지 주장** • 현재 미래에셋증권 연금저축과 IRP는 모두 언제든 중단·재개 가능 • 수령계좌·방법·금액·주기·상품매도순서를 모두 변경 가능 **검토 메모** • 현재 계좌의 중단은 일반 문서에서 간접 확인되지만 재개 직접 근거는 (구)개인연금저축에 한정됨.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 52. 미래에셋 MA-PP-030 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-030` 검색
- 질문: [개인연금] 타사의 연금계좌를 당사의 기존 연금계좌로 합칠 수 있나요?

**목표 답변**

> 제공 자료만으로는 타사의 연금계좌를 미래에셋증권의 기존 연금계좌에 합칠 수 있는지 일반적으로 확정할 수 없습니다. 다만 문서상 만 55세 이상인 경우 IRP로 받은 퇴직금을 연금저축으로 계좌이전할 수 있다고 안내되어 있고, 2013년 3월 1일 이후 DC 가입자는 2013년 3월 1일 이전 연금계좌로 퇴직금을 이체할 수 없다고 되어 있습니다. 따라서 계좌 종류(IRP·연금저축·DC), 나이, 최초 가입일과 연금개시 여부를 확인한 뒤 기존계좌 수관 가능 여부와 가입일 처리 기준을 별도로 확인해야 합니다.

**필수 주장**

- *MA-PP-030-C1** 만 55세 이상인 경우 IRP로 퇴직금을 받은 뒤 연금저축으로 계좌이전할 수 있다. 근거: E-DOC51-T11-210B5DF7C8FB684D, E-DOC51-T11-F2F3D134739C6D2E **MA-PP-030-C2** 2013년 3월 1일 이후 DC 가입자는 2013년 3월 1일 이전 연금계좌로 퇴직금을 이체할 수 없다. 근거: E-DOC39-T45-79ED6024E0CDD17D

**문서 근거·주의점**

- *E-DOC51-T11-210B5DF7C8FB684D** — [doc51.docx](https://docs.google.com/document/d/1ZglCHFrK68oDkGZkRKoDHlBQPahEbCiW/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc51` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `80befe4f1ad6cca530815c7d650d4a6e4ab22727d16f71fe72cb6461e9ecdf4a` · Docling JSON SHA-256 `1a637c0a62fc0f31a8218a3214e52795d008d04b98d6c9c21662f2b6d7de30f8` retrieval `knowledge-80befe4f1ad6-0002` 인용: “만 55세 이상이 되면 선택의 폭이 넓어진다.” **E-DOC51-T11-F2F3D134739C6D2E** — [doc51.docx](https://docs.google.com/document/d/1ZglCHFrK68oDkGZkRKoDHlBQPahEbCiW/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc51` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `80befe4f1ad6cca530815c7d650d4a6e4ab22727d16f71fe72cb6461e9ecdf4a` · Docling JSON SHA-256 `1a637c0a62fc0f31a8218a3214e52795d008d04b98d6c9c21662f2b6d7de30f8` retrieval `knowledge-80befe4f1ad6-0002` 인용: “IRP로 퇴직금 수령 후 연금저축으로 계좌를 이전하는 것은 자유롭게 가능하다.” **E-DOC39-T45-79ED6024E0CDD17D** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/45` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0005` 인용: “단, 2013년 3월 1일 이후 DC 가입자라면, 기존 2013년 3월 1일 이전 연금계좌로 퇴직금을 이체할 수 없으니 이 점은 유의하자.”

**부족 근거·금지 주장**

- *부족 근거** • 타사 연금계좌를 당사의 기존 연금계좌로 일반 수관할 수 있는지 • 신규 이전용 계좌와 기존 계좌의 차이 • 연금개시 계좌 수관 가능 여부 • 수관 후 적용되는 가입일 **금지 주장** • 타사 연금계좌는 신규계좌와 기존계좌 어디로든 항상 합칠 수 있다는 주장 • 수관 후 가입일이 무조건 당사 기존계좌 가입일로 바뀐다는 주장 • 연금개시 계좌에는 어떤 경우에도 이전할 수 없다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 53. 미래에셋 MA-PP-032 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-032` 검색
- 질문: [개인연금] 연금개시나 중도인출, 해지할 때 연금보험료등 소득·세액공제확인서를 꼭 제출해야하나요?

**목표 답변**

> 제공 자료에서 직접 확인되는 것은 DC·IRP의 과세재원을 확정할 때 국세청의 연금보험료등 소득·세액공제확인서가 필요하고 내점 처리한다는 내용입니다. 개인연금의 연금개시·해지·중도인출마다 이 서류가 반드시 필요한지, 중도인출 시 서류 없이 과세 처리할 수 있는지, 이연퇴직금만 있는 계좌의 예외가 있는지는 확인되지 않습니다. 따라서 업무 종류와 계좌 재원별 필수서류를 현행 기준으로 별도 확인해야 합니다.

**필수 주장**

- *MA-PP-032-C1** DC·IRP 과세재원확정의 필요서류로 연금보험료등 소득·세액공제확인서가 제시되어 있고, 재원확정은 내점 처리로 안내된다. 근거: E-DOC19-T0-0B917CE5C77479AA, E-DOC19-T5-CFA34208C6E93DC0, E-DOC19-T6-BF338AE84ED66DBE, E-DOC19-T8-40822561C08885E0

**문서 근거·주의점**

- *E-DOC19-T0-0B917CE5C77479AA** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/0` · label `text` · variant `delivery` page/slide `1`; charspan `0:20`; bbox `{"b":742.5152770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":214.97,"t":751.9479829101563}` retrieval `knowledge-18ac1b2650ae-0000` 인용: “퇴직연금 (DC/IRP) 과세재원확정” **E-DOC19-T5-CFA34208C6E93DC0** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/5` · label `section_header` · variant `delivery` page/slide `1`; charspan `0:12`; bbox `{"b":571.8752770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":164.66000000000003,"t":581.3079829101563}` 인용: “2. 재원확정 필요서류” **E-DOC19-T6-BF338AE84ED66DBE** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/6` · label `text` · variant `delivery` page/slide `1`; charspan `0:28`; bbox `{"b":545.2052770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":292.99592,"t":554.6379829101562}` retrieval `knowledge-18ac1b2650ae-0002` 인용: “-연금보험료등 소득·세액공제확인서 ( 국세청자료 )” **E-DOC19-T8-40822561C08885E0** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/8` · label `text` · variant `delivery` page/slide `1`; charspan `0:6`; bbox `{"b":491.92527702780336,"coord_origin":"BOTTOMLEFT","l":131.78,"r":186.74,"t":501.3579829101563}` 인용: “내점만 가능”

**부족 근거·금지 주장**

- *부족 근거** • 개인연금 연금개시·해지 시 서류의 필수성 • 중도인출 시 서류 미제출 처리 • 이연퇴직금만 있는 계좌의 예외 **금지 주장** • 개인연금 개시와 해지에는 항상 해당 서류가 필수라는 주장 • 중도인출은 언제나 16.5% 과세 후 서류 없이 가능하다는 주장 • 이연퇴직금만 있으면 무조건 서류가 면제된다는 주장 **검토 메모** • 인용 문서는 개인연금이 아니라 DC·IRP 과세재원확정 자료이므로 적용 범위를 확대하지 않음.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 54. 미래에셋 MA-PP-033 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-033` 검색
- 질문: [개인연금] 과거 세액공제 받지 않은 금액을 올해 납입금으로 전환할 수 있나요?

**목표 답변**

> 제공 자료에서 직접 확인되는 범위는 만기 ISA 전환납입액 중 세액공제대상금액을 제외한 나머지 금액이 전환 완료 다음 연도부터 비과세재원으로 반영되어 세액공제전환특례에 사용할 수 있다는 경우입니다. 일반적인 과거 미공제 납입액을 올해 납입액으로 전환할 수 있는지와 신청 요건·한도·절차는 자료로 확인되지 않습니다.

**필수 주장**

- *MA-PP-033-C1** 만기 ISA 전환납입액 중 세액공제대상금액을 제외한 나머지는 전환 완료 다음 연도부터 비과세재원으로 반영되어 세액공제전환특례가 가능하다. 근거: E-DOC33-T72-5F104F29BA1F6807

**문서 근거·주의점**

- *E-DOC33-T72-5F104F29BA1F6807** — [doc33.pptx](https://docs.google.com/presentation/d/1gF7eKVvP9VNjqDvQo4Z_n6lgmmFqCEO-/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc33` · `#/texts/72` · label `paragraph` · variant `delivery` page/slide `5`; charspan `0:226`; bbox `{"b":4314024.0,"coord_origin":"BOTTOMLEFT","l":680477.0,"r":11901633.0,"t":6032636.0}` retrieval `knowledge-0aba02f48732-0001` 인용: “- 전환완료 다음연도부터 만기ISA전환 납입액에서 세액공제대상금액을 제외한 나머지 금액은 비과세재원으로 반영, 인출 및 세액공제전환특례 가능합니다.”

**부족 근거·금지 주장**

- *부족 근거** • 일반 과거 납입액의 미공제 여부를 확인하는 기준 • 올해 납입액 전환 가능 범위와 한도 • 신청 채널·서류·시점 **금지 주장** • 모든 과거 미공제 납입액을 자동으로 올해 납입액으로 바꿀 수 있다는 주장 • 연금저축 600만원·IRP 900만원 초과분은 별도 확인 없이 전환된다는 주장 • 특정 모바일 메뉴에서 현재 신청 가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 55. 미래에셋 MA-PP-035 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-035` 검색
- 질문: [개인연금] 연금개시를 신청한 계좌에 추가 입금이 가능한가요?

**목표 답변**

> 제공 자료상 연금개시 계좌에는 개인납입금을 추가 불입할 수 없습니다. 퇴직금은 입금 가능한 재원으로 제시되지만, 실제로 개시 계좌에 퇴직금을 입금할 수 있는지는 금융회사 방침에 따라 달라질 수 있으므로 미래에셋증권의 현재 수관 가능 여부를 확인해야 합니다. 세액공제를 위한 개인납입이 필요하면 새로운 연금계좌를 개설해야 한다고 안내되어 있습니다.

**필수 주장**

- *MA-PP-035-C1** 연금이 개시된 IRP는 IRP 대표계좌번호로 일반 부담금을 입금할 수 없는 경우로 안내된다. 근거: E-DOC6-T10-DEC7250F4A07BDAE, E-DOC6-T12-9B6A483485E4B284 **MA-PP-035-C2** 개시된 연금계좌에는 개인납입금을 추가 불입할 수 없고 퇴직금 입금 가능 여부는 금융회사 방침에 따라 달라질 수 있다. 근거: E-DOC40-T23-141BF285F86E29EC, E-DOC40-T23-6F1F2C2AE965BA3D **MA-PP-035-C3** 세액공제를 위한 개인납입이 필요하면 새로운 연금계좌를 개설해야 한다. 근거: E-DOC40-T23-FCA2260A8165932A

**문서 근거·주의점**

- *E-DOC6-T10-DEC7250F4A07BDAE** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/10` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “가. IRP대표계좌번호로 입금이 불가한 경우” **E-DOC6-T12-9B6A483485E4B284** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/12` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “▶연금 개시된 IRP인 경우” **E-DOC40-T23-141BF285F86E29EC** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/23` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0004` 인용: “개시된 계좌로는 퇴직금에 한해 입금이 가능하고, 개인납입금을 추가 불입할 수 없다.” **E-DOC40-T23-6F1F2C2AE965BA3D** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/23` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0004` 인용: “또한 개시된 계좌로 퇴직금 입금이 가능한지 여부는 금융회사 방침에 따라 달라질 수 있으므로, 연금계좌를 보유한 금융회사에 먼저 확인하고 인출을 시작하자.” **E-DOC40-T23-FCA2260A8165932A** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/23` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0004` 인용: “세액공제를 위한 개인 납입이 필요하다면 새로운 연금계좌를 개설해야 한다.”

**부족 근거·금지 주장**

- *부족 근거** • 미래에셋증권의 현재 개시계좌 퇴직금 수관 방침과 세부 절차 **금지 주장** • 연금개시 후 개인납입금을 추가 입금할 수 있다는 주장 • 개시된 계좌에는 어떤 재원도 입금할 수 없다는 주장 • 퇴직금은 모든 개시계좌에 조건 없이 입금된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 56. 미래에셋 MA-PP-037 · 부분 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-037` 검색
- 질문: [개인연금] 연금저축과 구.개인연금은 무슨 차이가 있나요?

**목표 답변**

> (구)개인연금저축은 세액공제가 아니라 납입액의 40%를 연 72만원 한도로 소득공제하는 구조이고, 가입기간 10년 이상·만 55세 이후 개시·최소 5년 수령 요건을 지키면 이자소득이 비과세됩니다. 단일상품 투자 방식이고 중도인출은 불가능합니다. 현재 연금저축은 세액공제 방식이며 연금저축 단독 세액공제 대상 한도는 연 600만원이고, 연금저축펀드는 부분 인출이 가능합니다. 다만 제공 자료에는 두 제도의 정확한 판매기간, 신규가입 가능 여부, 2013년 3월 전후 연금저축계좌 구분이 없어 그 부분은 확정할 수 없습니다.

**필수 주장**

- *MA-PP-037-C1** (구)개인연금저축은 납입액의 40%를 연 72만원 한도로 소득공제하고, 가입기간 10년 이상·만 55세 이후·최소 5년 수령 요건을 충족하면 이자소득이 비과세된다. 근거: E-DOC25-T9-2D33C45D4E963066, E-DOC25-TB0-F01F75840C96C73D, E-DOC25-T10-76140F64FAECEE9F **MA-PP-037-C2** (구)개인연금저축은 단일상품 투자 방식이고 중도인출은 불가능하다. 근거: E-DOC25-TB0-E43ECD18BB8C88BE, E-DOC25-TB0-1465754DEB7A4D3F **MA-PP-037-C3** 현재 연금저축은 세액공제 방식으로 연금저축 단독 공제 대상 한도가 연 600만원이며 연금저축펀드는 부분 인출이 가능하다. 근거: E-DOC41-T7-33FD26DA8D31461B, E-DOC41-T12-4C768BB56D961387

**문서 근거·주의점**

- *E-DOC25-T9-2D33C45D4E963066** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/texts/9` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` retrieval `knowledge-5914e8bedc6b-0000` 인용: “매년 납입액의 40%를 소득공제 받을 수 있는데 소득공제 한도는 연 72만원이다.” **E-DOC25-TB0-F01F75840C96C73D** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/tables/0` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` table cells `r2c1` retrieval `knowledge-5914e8bedc6b-0002` 인용: “가입기간 10년 이상 & 만 55세 이후” **E-DOC25-T10-76140F64FAECEE9F** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/texts/10` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` retrieval `knowledge-5914e8bedc6b-0000` 인용: “55세이상이면 연금개시가 가능하고 5년 이상에 걸쳐 나누어 받아야 한다는 조건을 지켜야 한다. 그래야 늘어난 수익에 대해 비과세 혜택을 받을 수 있다.” **E-DOC25-TB0-E43ECD18BB8C88BE** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/tables/0` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` table cells `r8c1` retrieval `knowledge-5914e8bedc6b-0002` 인용: “단일상품 투자 (펀드 전환 가능)” **E-DOC25-TB0-1465754DEB7A4D3F** — [doc25.docx](https://docs.google.com/document/d/1HF6rBTVaFuTDqyt6uh-4Iijh8WnBeRSV/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc25` · `#/tables/0` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5914e8bedc6b9498ed2876f6dbc7fa1069bd71f9e58f8de2d64b5daa409caff4` · Docling JSON SHA-256 `79b610445adcb6ca42c3b3d16027730e94d24c470a121c8be9fab18e07f21d96` table cells `r9c1` 인용: “불가능” **E-DOC41-T7-33FD26DA8D31461B** — [doc41.docx](https://docs.google.com/document/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc41` · `#/texts/7` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0000` 인용: “세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.” **E-DOC41-T12-4C768BB56D961387** — [doc41.docx](https://docs.google.com/document/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc41` · `#/texts/12` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0001` 인용: “연금저축펀드는 부분 인출이 자유롭다.”

**부족 근거·금지 주장**

- *부족 근거** • (구)개인연금저축과 연금저축의 정확한 판매기간 • (구)개인연금저축 신규가입 가능 여부 • 2013년 3월 전후 연금저축계좌의 구분과 연금수령연차 **금지 주장** • (구)개인연금저축이 특정 연도에 판매 종료되었다는 주장 • 현재 신규가입이 불가능하다는 주장 • 2013년 3월 전후 계좌의 연금수령연차를 단정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 57. 미래에셋 MA-RP-002 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-002` 검색
- 질문: [퇴직연금] 퇴직연금/IRP 계좌로 입금이 안되는데 어떻게 해야 하죠?

**목표 답변**

> 개인형 IRP 기준으로 입금이 되지 않으면 먼저 입금 시각이 08:00~16:00인지, 연금이 이미 개시된 계좌인지, 납입가능한도를 초과했는지, 플랜등록 전이거나 계약이전·해지 처리 중인지 확인해야 합니다. 연금저축과 DC·IRP의 연간 납입한도는 전 금융기관을 합산해 관리되므로, 등록한 한도와 다른 금융기관 납입액도 함께 확인해야 합니다. 다만 회사가 납입하는 DB·DC 부담금의 오류 사유와 처리 절차는 이 자료만으로 모두 확인되지 않습니다.

**필수 주장**

- *MA-RP-002-C1** IRP 입금 불가 사유로 업무시간 외 입금, 연금개시 계좌, 납입한도 초과, 플랜등록 전 또는 계약이전·해지 처리 중인 경우가 제시된다. 근거: E-DOC6-T10-DEC7250F4A07BDAE, E-DOC6-T11-166FDCAA20AFA549, E-DOC6-T12-9B6A483485E4B284, E-DOC6-T13-39C45573BD522522, E-DOC6-T14-0C663C37146F8728 **MA-RP-002-C2** 연금저축과 DC·IRP의 납입한도는 합산 연 1,800만원이며 전 금융기관 합산 적용된다. 근거: E-DOC6-T45-F2A32C262F085F05, E-DOC6-T46-576E8695BF535CC2

**문서 근거·주의점**

- *E-DOC6-T10-DEC7250F4A07BDAE** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/10` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “가. IRP대표계좌번호로 입금이 불가한 경우” **E-DOC6-T11-166FDCAA20AFA549** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “▶입금업무시간(08시~16시) 외 입금하는 경우” **E-DOC6-T12-9B6A483485E4B284** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/12` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “▶연금 개시된 IRP인 경우” **E-DOC6-T13-39C45573BD522522** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/13` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “▶납입가능한도를 초과하여 입금하는 경우” **E-DOC6-T14-0C663C37146F8728** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/14` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0003` 인용: “▶플랜등록 전, 계약이전 혹은 계약해지 처리중인 경우” **E-DOC6-T45-F2A32C262F085F05** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/45` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “1) 연금저축과 DC/IRP 합산하여 연간 1,800만원까지 한도 설정 가능” **E-DOC6-T46-576E8695BF535CC2** — [doc6.docx](https://docs.google.com/document/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc6` · `#/texts/46` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9` retrieval `knowledge-0bc7cd31e0cb-0004` 인용: “2) 전 금융기관 합산 적용”

**부족 근거·금지 주장**

- *부족 근거** • 회사 납입 DB·DC 부담금의 오류 사유와 처리 절차 **금지 주장** • 업무시간과 한도만 확인하면 모든 입금 오류가 해결된다는 주장 • 다른 금융기관 납입액은 한도에 포함되지 않는다는 주장 • ETF 같은 상품을 IRP로 직접 입고할 수 있다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 58. 미래에셋 MA-RP-003 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-003` 검색
- 질문: [퇴직연금] 위험자산 투자한도 초과 안내(E-mail 및 SMS)를 받았습니다. 무슨 내용인가요?

**목표 답변**

> 계좌가 IRP라면 제공 자료상 일반 위험자산의 투자 비중은 전체 적립금의 70% 이내로 제한됩니다. 금융감독원 기준을 충족한 TDF는 DC·IRP에서 적립금의 100%까지 투자할 수 있는 예외가 있습니다. 다만 받은 초과 안내가 어느 계좌 유형과 어떤 자산 분류를 기준으로 발송됐는지, 발송 기준과 주기, 초과 후 즉시 매도 의무 또는 추가매수 제한이 어떻게 적용되는지는 확인되지 않습니다. 따라서 안내 수신만으로 매도 여부를 단정하면 안 됩니다.

**필수 주장**

- *MA-RP-003-C1** IRP의 일반 위험자산 투자 비중은 전체 적립금의 70% 이내로 제한된다. 근거: E-DOC14-T20-170AF509BFDAD204 **MA-RP-003-C2** 금융감독원장이 정한 조건을 충족한 TDF는 DC·IRP 적립금의 100%까지 투자할 수 있다. 근거: E-DOC53-T16-E5AD93D48338C54D

**문서 근거·주의점**

- *E-DOC14-T20-170AF509BFDAD204** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view?usp=drivesdk) source `doc14` · `#/texts/20` · label `list_item` · variant `delivery` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.” **E-DOC53-T16-E5AD93D48338C54D** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view?usp=drivesdk) source `doc53` · `#/texts/16` · label `list_item` · variant `delivery` page/slide `2`; charspan `0:83`; bbox `{"b":452.68527702780335,"coord_origin":"BOTTOMLEFT","l":74.064,"r":559.4200000000001,"t":480.5979829101563}` retrieval `knowledge-2e34c142aed8-0006` 인용: “-TDF 는 금융감독원장이 정한 조건을 충족한 경우 DC 와 IRP 적립금의 100% 투자 가능함 . (DB 는 무조 건 70% 까지만 투자가능 )”

**부족 근거·금지 주장**

- *부족 근거** • 안내가 발송된 계좌 유형과 위험자산 산정 대상 • 위험자산 초과 알림의 발송 기준과 반복 주기 • 초과 상태에서의 즉시 매도 의무 여부 • 초과 후 상품별 추가매수 제한 **금지 주장** • 안내를 받으면 즉시 위험자산을 매도해야 한다는 주장 • 안내를 받아도 아무 조치가 필요 없다는 주장 • 초과 5영업일 후와 매월 말에 반드시 발송된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 59. 미래에셋 MA-RP-006 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-006` 검색
- 질문: [퇴직연금] 타사에서 IRP퇴직연금 수령중에 있는데, 연금저축계좌로 이전하고싶은데 가능한가요?

**목표 답변**

> 제공 자료는 만 55세 이상인 경우 IRP로 퇴직금을 받은 뒤 연금저축으로 계좌이전할 수 있다는 범위까지만 확인합니다. 이미 연금수령 중인 타사 IRP를 미래에셋증권 연금저축으로 이전할 수 있는지, 이전 후 연금개시 상태가 유지되는지, 정기지급을 다시 신청해야 하는지와 추가입금 제한은 확인되지 않습니다. 따라서 현재 지급 중인 연금의 중단·재신청 조건까지 확인한 뒤 이전 여부를 판단해야 합니다.

**필수 주장**

- *MA-RP-006-C1** 만 55세 이상인 경우 IRP로 퇴직금을 받은 뒤 연금저축으로 계좌이전할 수 있다. 근거: E-DOC51-T11-210B5DF7C8FB684D, E-DOC51-T11-F2F3D134739C6D2E

**문서 근거·주의점**

- *E-DOC51-T11-210B5DF7C8FB684D** — [doc51.docx](https://docs.google.com/document/d/1ZglCHFrK68oDkGZkRKoDHlBQPahEbCiW/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc51` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `80befe4f1ad6cca530815c7d650d4a6e4ab22727d16f71fe72cb6461e9ecdf4a` · Docling JSON SHA-256 `1a637c0a62fc0f31a8218a3214e52795d008d04b98d6c9c21662f2b6d7de30f8` retrieval `knowledge-80befe4f1ad6-0002` 인용: “만 55세 이상이 되면 선택의 폭이 넓어진다.” **E-DOC51-T11-F2F3D134739C6D2E** — [doc51.docx](https://docs.google.com/document/d/1ZglCHFrK68oDkGZkRKoDHlBQPahEbCiW/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc51` · `#/texts/11` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `80befe4f1ad6cca530815c7d650d4a6e4ab22727d16f71fe72cb6461e9ecdf4a` · Docling JSON SHA-256 `1a637c0a62fc0f31a8218a3214e52795d008d04b98d6c9c21662f2b6d7de30f8` retrieval `knowledge-80befe4f1ad6-0002` 인용: “IRP로 퇴직금 수령 후 연금저축으로 계좌를 이전하는 것은 자유롭게 가능하다.”

**부족 근거·금지 주장**

- *부족 근거** • 연금수령 중인 IRP의 계약이전 허용 여부 • 이전 후 연금개시 상태와 정기지급 처리 • 추가입금 가능 여부 • 타사 계약·시스템 차이에 따른 제한 **금지 주장** • 연금수령 중인 IRP도 항상 연금저축으로 이전 가능하다는 주장 • 이전 후 정기지급이 자동으로 계속된다는 주장 • 이전 후 추가입금이 무조건 불가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 60. 미래에셋 MA-RP-008 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-008` 검색
- 질문: [퇴직연금] 타사에 퇴직연금 DC가 있는데, 미래에셋으로 이전 할 수 있는 방법을 알려주세요.

**목표 답변**

> 제공 자료에서 직접 확인되는 방법은 보유상품을 매도하지 않고 옮기는 DC 실물이전입니다. 이 경우 DC에서 DC로 같은 제도끼리 진행하며, 재직 중인 회사를 통해 신청해야 합니다. 먼저 회사 퇴직연금 담당자에게 미래에셋증권과 DC 규약이 체결되어 있는지 확인하고, 수관 금융기관이 보유 상품을 취급하는지도 확인해야 합니다. 보유상품을 매도해 현금으로 옮기는 일반 계약이전의 신청 절차·필요서류와 실물이전 불가 상품의 처리 방법은 제공 자료로 확인되지 않습니다.

**필수 주장**

- *MA-RP-008-C1** DC 실물이전은 DC에서 DC로 진행하고 재직 중인 회사를 통해 신청한다. 근거: E-DOC35-T5-CBD7A34FFEF3271E, E-DOC35-T8-660F985F352A2A64 **MA-RP-008-C2** DC 실물이전을 하려면 이전받는 금융기관이 보유 상품을 취급해야 한다. 근거: E-DOC35-T11-6C93C4A42BD70D63 **MA-RP-008-C3** 이수관 대상 금융기관에 DC 규약이 체결되지 않은 플랜은 실물이전 불가 사유에 해당한다. 근거: E-DOC34-TB2-1217060F27B29084, E-DOC34-TB2-44E09A83AEC9E2DF

**문서 근거·주의점**

- *E-DOC35-T5-CBD7A34FFEF3271E** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/5` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “DC제도 → DC제도” **E-DOC35-T8-660F985F352A2A64** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/8` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “DB,DC제도는 재직중인 회사를 통해서만 이전 신청 가능” **E-DOC35-T11-6C93C4A42BD70D63** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/11` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “이전하려는 금융기관이 보유중인 상품을 취급하고 있어야 함.” **E-DOC34-TB2-1217060F27B29084** — [doc34.xlsx](https://docs.google.com/spreadsheets/d/1Bm3TtoB8q8ObaLSQlPjWLW7_x68fr65_/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc34` · `#/tables/2` · label `table` · variant `delivery` page/slide `1`; charspan `0:0`; bbox `{"b":32.0,"coord_origin":"TOPLEFT","l":1.0,"r":3.0,"t":5.0}` table cells `r16c0` 인용: “16.규약 미체결” **E-DOC34-TB2-44E09A83AEC9E2DF** — [doc34.xlsx](https://docs.google.com/spreadsheets/d/1Bm3TtoB8q8ObaLSQlPjWLW7_x68fr65_/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc34` · `#/tables/2` · label `table` · variant `delivery` page/slide `1`; charspan `0:0`; bbox `{"b":32.0,"coord_origin":"TOPLEFT","l":1.0,"r":3.0,"t":5.0}` table cells `r16c1` 인용: “이수관 하고자 하는 금융기관에 DC 규약이 미체결 되어 있는 플랜의 가입자 조회 및 접수시”

**부족 근거·금지 주장**

- *부족 근거** • 보유상품을 매도해 현금으로 이전하는 일반 계약이전의 신청 절차와 필요서류 • 실물이전 불가 상품의 매도·현금이전 처리 • 현재 처리기간 **금지 주장** • 실물이전이 DC 이전의 유일한 방법이라는 주장 • 개인이 회사 경로 없이 DC 이전을 직접 신청할 수 있다는 주장 • 미래에셋증권이 취급하지 않는 상품도 그대로 이전된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 61. 미래에셋 MA-RP-009 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-009` 검색
- 질문: [퇴직연금] 퇴직연금DC/IRP계좌에서 채권거래가 가능한가요?

**목표 답변**

> 퇴직연금 DC·기업형IRP·개인형IRP에서는 M-STOCK으로 장외채권을 매수할 수 있습니다. 제공 문서상 매수 가능시간은 영업일 10:00~15:00이며, 모바일에서 매수·취소는 가능하지만 매도는 영업점 방문 또는 유선으로 처리합니다. 보유 현금성자산으로 매수하고 교체매매 방식은 지원하지 않습니다. 다만 이 문서는 국내 장내채권·해외채권의 거래 불가 여부와 수수료까지는 확인하지 않습니다.

**필수 주장**

- *MA-RP-009-C1** 퇴직연금 DC·기업형IRP·개인형IRP 계좌에서 M-STOCK으로 장외채권을 매수할 수 있다. 근거: E-DOC7-T0-7B150D2CF950FD6B, E-DOC7-T101-FDAE9E66FA1C9D0C, E-DOC7-T146-73F318CC5EFAFFE3, E-DOC7-T170-CA798518B7529DC0 **MA-RP-009-C2** 채권 매수 가능시간은 영업일 10:00~15:00이고 M-STOCK에서 매수·취소 가능하지만 매도는 영업점 또는 유선 처리한다. 근거: E-DOC7-T23-E597EFFA365613EA, E-DOC7-T25-B17472786BA4BDD9 **MA-RP-009-C3** 보유 현금성자산으로 채권을 매수하며 교체매매를 통한 매수는 불가하다. 근거: E-DOC7-T31-78EB1978D2FAB617

**문서 근거·주의점**

- *E-DOC7-T0-7B150D2CF950FD6B** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/0` · label `section_header` · variant `review_local_ocr` page/slide `1`; charspan `0:23`; bbox `{"b":349.3333333333333,"coord_origin":"BOTTOMLEFT","l":54.0,"r":511.3333333333333,"t":472.0}` 인용: “퇴직연금 장외채권 매수 모바일 신청 가이드” **E-DOC7-T101-FDAE9E66FA1C9D0C** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/101` · label `section_header` · variant `review_local_ocr` page/slide `6`; charspan `0:15`; bbox `{"b":440.66666666666663,"coord_origin":"BOTTOMLEFT","l":226.0,"r":554.6666666666667,"t":479.0}` 인용: “퇴직연금 장외채권 매수 신청” **E-DOC7-T146-73F318CC5EFAFFE3** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/146` · label `text` · variant `review_local_ocr` page/slide `6`; charspan `0:27`; bbox `{"b":92.33333333333331,"coord_origin":"BOTTOMLEFT","l":313.3333333333333,"r":485.3333333333333,"t":104.33333333333331}` retrieval `knowledge-082580b9fb6e-0033` 인용: “퇴직연금(DC 기업형RP [개인형RP) 계좌 선택” **E-DOC7-T170-CA798518B7529DC0** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/170` · label `text` · variant `review_local_ocr` page/slide `6`; charspan `0:4`; bbox `{"b":286.0,"coord_origin":"BOTTOMLEFT","l":595.0,"r":628.3333333333333,"t":298.0}` 인용: “장외채권” **E-DOC7-T23-E597EFFA365613EA** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/23` · label `text` · variant `review_local_ocr` page/slide `2`; charspan `0:55`; bbox `{"b":273.0,"coord_origin":"BOTTOMLEFT","l":130.66666666666666,"r":554.0,"t":289.66666666666663}` retrieval `knowledge-082580b9fb6e-0002` 인용: “채권 매수 가능시간은 10:00~15.00(영업일 기준입니다. X 15.00 이후 매수 취소 불가” **E-DOC7-T25-B17472786BA4BDD9** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/25` · label `text` · variant `review_local_ocr` page/slide `2`; charspan `0:65`; bbox `{"b":190.0,"coord_origin":"BOTTOMLEFT","l":130.66666666666666,"r":646.6666666666666,"t":206.0}` retrieval `knowledge-082580b9fb6e-0003` 인용: “모바일(M-STOCK)로 채권 매수. 취소는 가능하지만, 매도는 불가합니다. X 매도 : 영업점 방문 or 유선 처리” **E-DOC7-T31-78EB1978D2FAB617** — [doc7.pdf](https://drive.google.com/file/d/1SeGtYPU0_diYe6U1zk0yVgEfqlWoq_XU/view?usp=drivesdk) source `doc7` · `#/texts/31` · label `text` · variant `review_local_ocr` page/slide `2`; charspan `0:45`; bbox `{"b":12.0,"coord_origin":"BOTTOMLEFT","l":131.0,"r":530.3333333333333,"t":29.333333333333314}` retrieval `knowledge-082580b9fb6e-0005` 인용: “보유한 현금성자산으로 채권 매수가 가능합니다. X 교체매매틀 통한 채권 매수 불가”

**부족 근거·금지 주장**

- *부족 근거** • 국내 장내채권·해외채권 거래 제한 • 장외채권 매매 수수료 **금지 주장** • 국내 장외채권만 거래 가능 • 국내 장내채권과 해외채권은 모두 거래 불가능 • 장외채권 매매 수수료가 없다 **검토 메모** • legacy OCR의 'RP'는 동일 SHA 원본 PDF에서 'IRP'로 확인한 parser drift다. • legacy knowledge bundle: doc7--082580b9fb6e--docling-local-ocr-v1

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 62. 미래에셋 MA-RP-017 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-017` 검색
- 질문: [퇴직연금] IRP계좌에 보유중인 상품내역에 미래에셋 현금성자산이라고 있는데 어떤 상품인가요?

**목표 답변**

> 제공 자료상 현금성자산으로 표시될 수 있는 경우에는 부담금 투자비율과 디폴트옵션을 모두 지정하지 않은 자금, 디폴트옵션 적용 대기 중인 자금 등이 있습니다. 따라서 보유내역의 명칭만으로 정확한 상품을 특정할 수 없습니다. 디폴트옵션 적용 대기 중인 현금성자산의 금리는 매일 변동해 사전 안내가 어렵지만, 이 자산이 1일물 CMA 또는 MMDA인지와 현재 금리·조회 경로는 제공 자료로 확인되지 않습니다.

**필수 주장**

- *MA-RP-017-C1** 부담금 투자비율을 등록하지 않고 디폴트옵션도 지정하지 않으면 자금은 현금성자산으로 운용된다. 근거: E-DOC55-T82-BBC436D130CE9015 **MA-RP-017-C2** 디폴트옵션 대기기간의 현금은 현금성자산으로 운용되고 금리는 매일 변동해 사전 안내가 어렵다. 근거: E-DOC29-TB4-867A30EADAA7A93F, E-DOC29-TB4-90BCCA87ADCBC564

**문서 근거·주의점**

- *E-DOC55-T82-BBC436D130CE9015** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/82` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0004` 인용: “부담금 투자비율 미등록 및 디폴트옵션을 지정하지 않은 경우 현금성자산으로 운용되며” **E-DOC29-TB4-867A30EADAA7A93F** — [doc29.xlsx](https://docs.google.com/spreadsheets/d/1ji_KwCD9UfF6Wx5mx5BK9yE_spVymQx3/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc29` · `#/tables/4` · label `table` · variant `delivery` page/slide `2`; charspan `0:0`; bbox `{"b":101.0,"coord_origin":"TOPLEFT","l":0.0,"r":8.0,"t":0.0}` table cells `r39c4` retrieval `knowledge-c1d3b647f178-0038` 인용: “대기기간 동안의 현금은 대기성자금(현금성자산)으로 운용됩니다.” **E-DOC29-TB4-90BCCA87ADCBC564** — [doc29.xlsx](https://docs.google.com/spreadsheets/d/1ji_KwCD9UfF6Wx5mx5BK9yE_spVymQx3/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc29` · `#/tables/4` · label `table` · variant `delivery` page/slide `2`; charspan `0:0`; bbox `{"b":101.0,"coord_origin":"TOPLEFT","l":0.0,"r":8.0,"t":0.0}` table cells `r39c4` retrieval `knowledge-c1d3b647f178-0038` 인용: “대기성자금의 금리는 매일 변동 되어 사전안내가 불가합니다.”

**부족 근거·금지 주장**

- *부족 근거** • 현금성자산의 구체 상품이 1일물 CMA 또는 MMDA인지 • 현재 적용금리 • 금리 조회 메뉴와 조회 가능 시각 **금지 주장** • 현금성자산이 언제나 운용지시되지 않은 대기자금이라는 주장 • 현금성자산이 반드시 1일물 CMA 또는 MMDA라는 주장 • 연 2.35~2.75%가 현재 적용된다는 주장 • 특정 시각 이후 조회 가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 63. 미래에셋 MA-RP-020 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-020` 검색
- 질문: [퇴직연금] 예금 만기 시 다시 예금으로 자동매수하는 방법이 있나요?

**목표 답변**

> 만기 전에 만기예약매수로 다음 운용상품을 미리 지정하는 방식은 가능합니다. 이 예약은 자동 재예치가 아니라 가입자가 미리 한 일회성 운용지시로 보며, 기존과 같은 원리금보장상품을 계속 운용하도록 지정할 수도 있습니다. 다만 신청 마감이 만기 2영업일 전인지, M-STOCK·홈페이지의 현재 경로, 저축은행예금의 지정 가능 기간과 판매중지·한도소진 때의 처리는 제공 자료로 확인되지 않습니다.

**필수 주장**

- *MA-RP-020-C1** 만기예약매수는 가입자가 미리 하는 일회성 운용지시이며, 기존과 같은 원리금보장상품을 계속 운용하도록 지정할 수 있다. 근거: E-DOC29-TB4-A5D92833FF922339

**문서 근거·주의점**

- *E-DOC29-TB4-A5D92833FF922339** — [doc29.xlsx](https://docs.google.com/spreadsheets/d/1ji_KwCD9UfF6Wx5mx5BK9yE_spVymQx3/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc29` · `#/tables/4` · label `table` · variant `delivery` page/slide `2`; charspan `0:0`; bbox `{"b":101.0,"coord_origin":"TOPLEFT","l":0.0,"r":8.0,"t":0.0}` table cells `r45c4` retrieval `knowledge-c1d3b647f178-0044` 인용: “일회적으로 미리 정해 두는 만기예약매수는 가입자가 스스로 한 운용지시로 볼 수 있어 자동 재예치와는 구별됩니다. 따라서 기존과 같은 원리금보장상품을 계속 운용하는 것도 가능합니다.”

**부족 근거·금지 주장**

- *부족 근거** • 만기예약매수 신청 마감시각 • 현재 M-STOCK·홈페이지 신청 경로 • 저축은행예금 지정 가능 기간 • 판매중지·한도소진 시 처리 **금지 주장** • 만기 2영업일 전까지 반드시 신청할 수 있다는 주장 • 저축은행예금은 만기 15일 이내 상품만 지정 가능하다는 주장 • 매수 불가 시 항상 현금성자산으로 운용된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 64. 미래에셋 MA-RP-023 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-023` 검색
- 질문: [퇴직연금] 디폴트옵션을 지정해도 ETF/펀드 매매가 가능한가요?

**목표 답변**

> 디폴트옵션을 지정했더라도 ETF는 직접 매매할 수 있습니다. 제공 문서상 DC·IRP 가입자는 미래에셋증권 홈페이지나 모바일 앱에서 ETF를 직접 매매할 수 있고, 만기가 없는 실적배당형 상품은 디폴트옵션 때문에 자동 전환되지 않습니다. 다만 같은 근거에서 일반 펀드의 구체적인 매수·매도 경로와 신규 입금액의 자동매수 조건까지는 확인되지 않습니다.

**필수 주장**

- *MA-RP-023-C1** DC·IRP 가입자는 미래에셋증권 홈페이지 또는 모바일 앱에서 ETF를 직접 매매할 수 있다. 근거: E-DOC53-T10-4ED941F5C6BAFE67 **MA-RP-023-C2** 만기가 없는 실적배당형 상품은 디폴트옵션으로 자동 전환되지 않는다. 근거: E-DOC29-TB4-A5B987676F761358

**문서 근거·주의점**

- *E-DOC53-T10-4ED941F5C6BAFE67** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view?usp=drivesdk) source `doc53` · `#/texts/10` · label `list_item` · variant `delivery` page/slide `1`; charspan `0:45`; bbox `{"b":383.40645349839156,"coord_origin":"BOTTOMLEFT","l":56.04,"r":437.35,"t":393.86198291015626}` retrieval `knowledge-2e34c142aed8-0000` 인용: “DC/IRP 가입자가 당사 홈페이지 or 모바일 App 을 통해 직접 매매 가능” **E-DOC29-TB4-A5B987676F761358** — [doc29.xlsx](https://docs.google.com/spreadsheets/d/1ji_KwCD9UfF6Wx5mx5BK9yE_spVymQx3/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc29` · `#/tables/4` · label `table` · variant `delivery` page/slide `2`; charspan `0:0`; bbox `{"b":101.0,"coord_origin":"TOPLEFT","l":0.0,"r":8.0,"t":0.0}` table cells `r91c4` retrieval `knowledge-c1d3b647f178-0090` 인용: “만기가 없는 실적배당형 상품만 보유 중인 경우에는 그 적립금에 디폴트옵션이 자동 적용되지 않습니다.”

**부족 근거·금지 주장**

- *부족 근거** • 일반 펀드의 구체적 매매 경로 • 신규 입금액에 디폴트옵션이 적용되는 가입시점·입금매수상품 조건 **금지 주장** • 모든 펀드가 언제나 제한 없이 매매된다는 주장 • 2022년 12월 2일 전후 가입자 처리 차이를 근거 없이 단정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 65. 미래에셋 MA-RP-027 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-027` 검색
- 질문: [퇴직연금] 퇴직연금 잔고확인은 어떻게 하나요?

**목표 답변**

> 제공 문서에서 직접 확인되는 조회 방법은 사무담당자용 PC 온라인 서비스의 DB 잔고조회·수익률조회입니다. 이 경로에서는 현재 퇴직연금 적립금 운용현황을 바로 확인할 수 있습니다. 개인 DC·IRP 가입자가 M-STOCK이나 홈페이지에서 조회하는 정확한 메뉴와 화면별 평가기준은 문서 근거가 없어 단정할 수 없습니다.

**필수 주장**

- *MA-RP-027-C1** DB 사무담당자용 온라인 서비스에서는 잔고조회와 수익률조회로 현재 적립금 운용현황을 확인할 수 있다. 근거: E-DOC55-T1127-B860E9A6C4037D6C, E-DOC55-T1128-280A9CC2608CDB77

**문서 근거·주의점**

- *E-DOC55-T1127-B860E9A6C4037D6C** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/1127` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0075` 인용: “회사가 퇴직금 운용을 담당하는 DB제도는 『잔고조회』, 『수익률조회』를 통해 현재 퇴직연금 적립금” **E-DOC55-T1128-280A9CC2608CDB77** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/1128` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0075` 인용: “운용현황도 즉시 확인 가능하고”

**부족 근거·금지 주장**

- *부족 근거** • 개인 DC·IRP의 M-STOCK·홈페이지 상세 경로 • ETF와 금융상품 화면의 잔고 평가시점 차이 • 간편조회 서비스 조건 **금지 주장** • 개인 가입자용 앱 경로를 DB 사무담당자용 경로와 동일하다고 단정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 66. 미래에셋 MA-RP-028 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-028` 검색
- 질문: [퇴직연금] 퇴직연금 MP 구독서비스는 무엇인가요?

**목표 답변**

> MP 구독은 DC·기업형IRP와 개인형IRP 가입자(DB 제외)를 대상으로 포트폴리오 전략을 알림으로 제공하고, 가입자가 승인하면 보유 펀드·현금을 위험자산 한도 안에서 MP 비율로 리밸런싱하는 서비스입니다. 투자일임형 자동운용은 아니어서 구독 신청·부담금 납입·약 2~3개월 주기의 리밸런싱 이벤트마다 가입자가 직접 승인해야 합니다. 신청과 취소는 M-STOCK의 연금포트폴리오 > 퇴직연금 MP구독서비스에서 할 수 있습니다. 수수료, 최소 가입금액, 취소 패널티는 제공 문서에서 확인되지 않습니다.

**필수 주장**

- *MA-RP-028-C1** MP 구독서비스 대상은 DC·기업형IRP와 개인형IRP 가입자이며 DB는 제외된다. 근거: E-DOC54-T14-9647AA64358BD571 **MA-RP-028-C2** 포트폴리오 전략을 알림으로 제공하고 가입자가 승인하면 펀드·현금을 MP 비율로 리밸런싱한다. 근거: E-DOC54-T362-1C58099E15DD0294, E-DOC54-T371-734A4D26A2603188, E-DOC54-T407-984A1F60FB1813B1 **MA-RP-028-C3** 투자일임형 자동운용이 아니라 매 리밸런싱 이벤트마다 가입자가 직접 승인하는 부수 서비스다. 근거: E-DOC54-T441-AE933F563DEC8E3A, E-DOC54-T442-A93E7E9B4AB2AAAB **MA-RP-028-C4** 신청·취소는 M-STOCK 퇴직연금 MP구독서비스 메뉴에서 한다. 근거: E-DOC54-T22-93E0A39706979F76, E-DOC54-T24-BD9102CED64C24AA

**문서 근거·주의점**

- *E-DOC54-T14-9647AA64358BD571** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/14` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:45`; bbox `{"b":476.57142857142856,"coord_origin":"BOTTOMLEFT","l":55.61904761904762,"r":331.8095238095238,"t":488.4761904761905}` retrieval `knowledge-09bf3b31d82e-0002` 인용: “-당사 퇴직연금 가입자(DC·기업형IRP, 개인형IRP)입니다.(단, DB 불가)” **E-DOC54-T362-1C58099E15DD0294** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/362` · label `text` · variant `review_local_ocr` page/slide `10`; charspan `0:82`; bbox `{"b":426.0952380952381,"coord_origin":"BOTTOMLEFT","l":174.0,"r":305.42857142857144,"t":458.4761904761905}` retrieval `knowledge-09bf3b31d82e-0025` 인용: “[미래에셋증권] 퇴직연금 포트폴리오(MP) 도착 #{고객명} 고객님 #{제도유형}, #{계좌번호} #{상품명} 포트폴리오(MP) 전략이 도착했어요.” **E-DOC54-T371-734A4D26A2603188** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/371` · label `list_item` · variant `review_local_ocr` page/slide `10`; charspan `0:56`; bbox `{"b":322.28571428571433,"coord_origin":"BOTTOMLEFT","l":174.0,"r":448.76190476190476,"t":330.8571428571429}` retrieval `knowledge-09bf3b31d82e-0026` 인용: “고객이 보유한 펀드, 현금을 대상으로 위험자산 한도 범위 내에서 MP 비율에 맞춰 리밸런싱 진행” **E-DOC54-T407-984A1F60FB1813B1** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/407` · label `list_item` · variant `review_local_ocr` page/slide `13`; charspan `0:75`; bbox `{"b":478.57142857142856,"coord_origin":"BOTTOMLEFT","l":55.61904761904762,"r":541.3333333333333,"t":490.0}` retrieval `knowledge-09bf3b31d82e-0030` 인용: “-MP 구독 신청 시, 부담금 납입 시, 리밸런싱(약 2~3개월 주기) 이벤트 발생 시 리밸런싱을 진행(가입자가 MP 승인 시)합니다.” **E-DOC54-T441-AE933F563DEC8E3A** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/441` · label `list_item` · variant `review_local_ocr` page/slide `14`; charspan `0:83`; bbox `{"b":110.04761904761904,"coord_origin":"BOTTOMLEFT","l":55.61904761904762,"r":668.4761904761905,"t":121.95238095238096}` retrieval `knowledge-09bf3b31d82e-0040` 인용: “-MP 구독 서비스는 자본시장법 상의 자문이나 투자일임을 받아 직접 운용하는 랩어카운트 상품과는 다른 것으로, 상품 판매과정의 부수적인 서비스입니다.” **E-DOC54-T442-A93E7E9B4AB2AAAB** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/442` · label `list_item` · variant `review_local_ocr` page/slide `14`; charspan `0:45`; bbox `{"b":96.23809523809524,"coord_origin":"BOTTOMLEFT","l":55.61904761904762,"r":382.76190476190476,"t":107.1904761904762}` retrieval `knowledge-09bf3b31d82e-0040` 인용: “-따라서 리밸런싱 이벤트 발생 시마다 가입자가 직접 MP 승인을 진행해야 합니다.” **E-DOC54-T22-93E0A39706979F76** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/22` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:88`; bbox `{"b":238.52380952380952,"coord_origin":"BOTTOMLEFT","l":55.42857142857143,"r":693.047619047619,"t":250.90476190476193}` retrieval `knowledge-09bf3b31d82e-0005` 인용: “-M-STOCK: ① 메뉴-연금-연금-연금매매-퇴직연금 랩 해지(퇴직연금 랩 가입자), 2 메뉴-연금-연금포트폴리오-퇴직연금 MP구독서비스-MP구독서비스 가입” **E-DOC54-T24-BD9102CED64C24AA** — [doc54.pdf](https://drive.google.com/file/d/13yRnTXKdS0X9X6nK9uQyr-k7stmQB2OE/view?usp=drivesdk) source `doc54` · `#/texts/24` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:45`; bbox `{"b":202.8095238095238,"coord_origin":"BOTTOMLEFT","l":55.42857142857143,"r":393.5238095238095,"t":214.71428571428572}` retrieval `knowledge-09bf3b31d82e-0006` 인용: “-M-STOCK: 메뉴-연금-연금포트폴리오-퇴직연금 MP구독서비스-구독 관리/취소”

**부족 근거·금지 주장**

- *부족 근거** • MP 구독서비스 수수료 • 최소 가입금액 • 취소 패널티 **금지 주장** • MP 구독서비스 수수료가 무료 • 최소 가입금액이 없다 • 구독 취소에 아무런 패널티가 없다 • 가입자 승인 없이 자동으로 리밸런싱한다 • 카카오톡으로만 제공한다 **검토 메모** • 카카오톡 실패 시 SMS/MMS 전환 가능하므로 카카오톡 전용으로 표현하지 않았다. • legacy knowledge bundle: doc54--09bf3b31d82e--docling-naver-ocr-v1

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 67. 미래에셋 MA-RP-029 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-029` 검색
- 질문: [퇴직연금] 퇴직연금/IRP 수수료가 궁금합니다

**목표 답변**

> 퇴직연금 수수료는 연 1회 납부되고, 사무처리 온라인 서비스의 「수수료 납입내역조회」에서 납부 현황을 확인할 수 있습니다. 다만 제공 문서에는 IRP 개설 채널별 면제 여부, DC·DB 적립금 구간별 요율, ETF 매매수수료가 직접 제시되지 않아 구체 요율이나 “평생 무료” 여부는 단정할 수 없습니다.

**필수 주장**

- *MA-RP-029-C1** 퇴직연금 수수료는 연 1회 납부되며 온라인 서비스에서 납부 현황을 조회할 수 있다. 근거: E-DOC55-T1124-614F1AC92F3CACE4

**문서 근거·주의점**

- *E-DOC55-T1124-614F1AC92F3CACE4** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/1124` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0075` 인용: “『수수료 납입내역조회』에서 연 1회 납부되는 퇴직연금 수수료 현황도 확인 가능하고”

**부족 근거·금지 주장**

- *부족 근거** • IRP 개설·관리점별 수수료 면제 조건 • DC·DB 적립금 구간별 운용·자산관리 수수료율 • ETF 매매수수료 여부와 현재 공시 요율 **금지 주장** • 비대면 IRP가 모두 평생 무료라는 주장 • 퇴직연금 ETF 매매수수료가 언제나 0원이라는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 68. 미래에셋 MA-RP-030 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-030` 검색
- 질문: [퇴직연금] IRP계좌에서 연금은 어떻게 수령하나요?

**목표 답변**

> IRP에서 세제상 연금수령으로 인정받으려면 원칙적으로 가입기간 5년 이상, 만 55세 이후, 연간 연금수령한도 이내라는 요건을 지켜야 합니다. 다만 계좌에 퇴직금이 있으면 5년 가입기간 요건은 적용되지 않습니다. 연간 한도는 금융회사 앱이나 고객센터에서 확인할 수 있습니다. 기간지정·금액지정·비정기연금 등 구체적인 지급 방식의 종류와 신청 경로는 제공 문서에서 확인되지 않습니다.

**필수 주장**

- *MA-RP-030-C1** 연금수령은 가입기간 5년 이상, 만 55세 이후, 연간 연금수령한도 이내 인출이어야 하며 퇴직금이 있으면 가입기간 요건이 사라진다. 근거: E-DOC39-T3-C2C0176F8DF081DA **MA-RP-030-C2** 연금수령한도는 금융회사 앱이나 고객센터에서 확인할 수 있다. 근거: E-DOC39-T8-69A5593669B098D1

**문서 근거·주의점**

- *E-DOC39-T3-C2C0176F8DF081DA** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0000` 인용: “연금수령이란 먼저, 연금계좌 가입기간 5년 이상이면서 둘째, 만55세 이후에 인출해야 하고, 마지막으로 연간 연금수령한도 이내에서 인출하여야 한다. 연금계좌에 퇴직금이 있을 경우 가입기간 요건은 사라진다.” **E-DOC39-T8-69A5593669B098D1** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/8` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0001` 인용: “금융회사 앱이나 고객센터를 통해 매년 연금수령한도 금액을 확인할 수 있다.”

**부족 근거·금지 주장**

- *부족 근거** • 기간지정·금액지정·연금수령한도 방식·비정기연금의 정의 • 미래에셋증권의 구체적인 연금개시 신청 경로 **금지 주장** • 연금수령 방식이 정확히 네 가지라고 근거 없이 확정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 69. 미래에셋 MA-RP-031 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-031` 검색
- 질문: [퇴직연금] 연금개시 후에도 상품을 계속 운용할 수 있나요? 연금지급 매도순위는 어떻게 되나요?

**목표 답변**

> 연금개시 후에도 계좌에 남은 자금은 연금계좌 안에서 과세이연 상태로 계속 운용할 수 있습니다. 다만 제공 문서에는 연금 지급을 위한 자동 매도순위나 ETF·리츠의 자동매도 가능 여부가 직접 정리되어 있지 않으므로, 현금성자산→원리금보장상품→펀드 순서라고 단정할 수는 없습니다.

**필수 주장**

- *MA-RP-031-C1** 연금개시 후 인출하지 않은 자금은 연금계좌 안에서 과세이연 상태로 계속 운용할 수 있다. 근거: E-DOC40-T16-C51138A787595399

**문서 근거·주의점**

- *E-DOC40-T16-C51138A787595399** — [doc40.docx](https://docs.google.com/document/d/14l76_9dSWOtyatk-ktX7uCZlN-qHS0WE/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc40` · `#/texts/16` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fc1eadedd81bc5a693b626aaf9c47d3f91c793804b53cec0abb342aad6bd6a9b` · Docling JSON SHA-256 `5c8f5d85686bca682484049239cb8d122ddbd9e976c6b36a7b89b28d6c93d8ad` retrieval `knowledge-fc1eadedd81b-0003` 인용: “연금 개시를 신청하되 초반 10년은 최소 금액만 연금으로 수령해 실수령연차를 쌓고, 나머지 자금은 연금계좌 안에서 과세이연 상태로 운용하라.”

**부족 근거·금지 주장**

- *부족 근거** • 연금 지급용 매도순위 • 매도순위 미지정 시 자동 처리 규칙 • ETF·리츠의 자동매도 가능 여부 **금지 주장** • 현금성자산→원리금보장상품→펀드 순서가 문서로 확정됐다는 주장 • ETF·리츠는 반드시 직접 매도해야 한다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 70. 미래에셋 MA-RP-036 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-036` 검색
- 질문: [퇴직연금] 연간 납입한도 1,800만원 때문에 퇴직금 입금이 제한되지 않나요?

**목표 답변**

> 제공 문서상 연 1,800만원 한도는 가입자가 직접 넣는 가입자부담금에 적용됩니다. 반면 퇴직급여는 회사와 퇴직연금사업자가 원천징수영수증과 과세이연 내역을 별도로 처리하는 재원으로 구분됩니다. 따라서 개인 추가납입 한도와 퇴직급여 이전은 같은 항목으로 보지 않는 것이 타당하지만, “퇴직금은 금액 제한 없이 입금 가능”이라는 직접 문구는 확인되지 않아 그 표현까지 단정하지는 않습니다.

**필수 주장**

- *MA-RP-036-C1** 연 1,800만원 한도는 가입자가 납입하는 가입자부담금에 적용된다. 근거: E-DOC55-T171-5E2650B16795A9FF **MA-RP-036-C2** 퇴직급여 이전은 원천징수영수증과 과세이연 내역을 계좌에 등록해 처리한다. 근거: E-DOC55-T370-8B35F741282EF7ED, E-DOC55-T375-AC3030959B00CE94

**문서 근거·주의점**

- *E-DOC55-T171-5E2650B16795A9FF** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/171` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0008` 인용: “가입자가 납입하는 부담금으로 연간 최대 1,800만원까지 입금 가능하며,” **E-DOC55-T370-8B35F741282EF7ED** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/370` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0028` 인용: “퇴직자에 대한 퇴직소득원천징수영수증 작성하여 IRP계좌의 사업자에게 FAX 송부.” **E-DOC55-T375-AC3030959B00CE94** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/375` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0028` 인용: “원천천징수영수증을 수령, 과세이연 내역을 계좌정보에 입력한 후 부담금 입금.”

**부족 근거·금지 주장**

- *부족 근거** • 퇴직금 이전금액에 1,800만원 한도가 적용되지 않는다는 직접 문구 • 퇴직급여 유형별 제출서류 전체 **금지 주장** • 모든 퇴직금이 증빙 없이 무제한 입금된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 71. 미래에셋 MA-RP-039 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-039` 검색
- 질문: [퇴직연금] IRP계좌 해지는 어떻게 하나요?

**목표 답변**

> 제공 문서에서는 IRP 해지 신청의 홈페이지·모바일·유선 경로를 직접 확인할 수 없습니다. 다만 전액 해지는 연금외수령이므로 세액공제 받은 납입금과 운용수익에는 16.5% 기타소득세가 적용되고, 이연퇴직소득에는 퇴직소득 과세기준이 적용됩니다. 세액공제를 받지 않은 납입금이 있다면 국세청의 「연금보험료등 소득·세액공제확인서」로 재원확정을 해야 하며, 제공 문서상 이 재원확정은 내점만 가능합니다.

**필수 주장**

- *MA-RP-039-C1** 세액공제 납입금과 운용수익을 연금외수령하면 16.5% 기타소득세가 적용된다. 근거: E-DOC39-T22-18DB6C3F5E491C9F **MA-RP-039-C2** 이연퇴직소득을 연금외수령하면 기존 퇴직소득세가 적용된다. 근거: E-DOC39-T18-3E392AF503AC843E **MA-RP-039-C3** 재원확정에는 국세청의 연금보험료등 소득·세액공제확인서가 필요하고 내점만 가능하다. 근거: E-DOC19-T6-0F45A112BE925C85, E-DOC19-T8-40822561C08885E0

**문서 근거·주의점**

- *E-DOC39-T22-18DB6C3F5E491C9F** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/22` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0003` 인용: “세액공제 납입금과 운용수익에서 한도 초과하는 수령하는 금액은 연금외수령으로 분류된다. 전액 16.5% 기타소득세가 부과된다.” **E-DOC39-T18-3E392AF503AC843E** — [doc39.docx](https://docs.google.com/document/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc39` · `#/texts/18` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27` retrieval `knowledge-fcf61c7874ab-0002` 인용: “다만 연금수령한도를 초과한다면 초과분에 대해서는 기존 퇴직소득세 그대로 납부해야 한다.” **E-DOC19-T6-0F45A112BE925C85** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/6` · label `text` · variant `delivery` page/slide `1`; charspan `0:28`; bbox `{"b":545.2052770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":292.99592,"t":554.6379829101562}` retrieval `knowledge-18ac1b2650ae-0002` 인용: “연금보험료등 소득·세액공제확인서 ( 국세청자료 )” **E-DOC19-T8-40822561C08885E0** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view?usp=drivesdk) source `doc19` · `#/texts/8` · label `text` · variant `delivery` page/slide `1`; charspan `0:6`; bbox `{"b":491.92527702780336,"coord_origin":"BOTTOMLEFT","l":131.78,"r":186.74,"t":501.3579829101563}` 인용: “내점만 가능”

**부족 근거·금지 주장**

- *부족 근거** • IRP 해지 신청의 홈페이지·M-STOCK·유선 상세 경로 • 약정계좌·보안매체에 따른 출금 절차 **금지 주장** • 과세재원 확인 없이 모든 납입금에 일률적으로 16.5%를 부과한다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 72. 미래에셋 MA-RP-040 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-040` 검색
- 질문: [퇴직연금] 상품매매내역 조회는 어떻게 하나요?

**목표 답변**

> 제공 문서에서 확인되는 경로는 DB 사무담당자용 PC 온라인 서비스의 「상품매매 → 매매내역조회」입니다. 개인 DC·IRP 가입자가 M-STOCK이나 홈페이지에서 조회하는 정확한 메뉴는 Docling 근거에 없어 단정할 수 없습니다.

**필수 주장**

- *MA-RP-040-C1** DB 사무담당자용 PC 온라인 서비스의 상품매매 영역에는 매매내역조회 기능이 있다. 근거: E-DOC55-TB7-F975DE117DDDBCF5

**문서 근거·주의점**

- *E-DOC55-TB7-F975DE117DDDBCF5** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/tables/7` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` table cells `r1c5` retrieval `knowledge-a27d15fc4a66-0074` 인용: “상품검색 상품매수.매도 매매내역조회 부담금 투자비율 변경 만기상품예약매수 투자한도초과현황”

**부족 근거·금지 주장**

- *부족 근거** • 개인 DC·IRP의 M-STOCK·홈페이지 상세 조회 경로 **금지 주장** • DB 사무담당자용 메뉴를 개인 IRP 앱 메뉴와 동일하다고 단정하는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 73. 미래에셋 MA-RP-041 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-041` 검색
- 질문: [퇴직연금] 운용중인 상품변경은 어떻게 하나요?

**목표 답변**

> 현재 보유한 ETF는 DC·IRP 가입자가 홈페이지나 모바일 앱에서 직접 매매해 변경할 수 있습니다. DB 사무담당자용 온라인 서비스에는 상품매수·매도와 부담금 투자비율 변경 기능도 있습니다. 다만 개인 IRP의 일반 금융상품 매도·매수 경로, 향후 입금될 부담금의 사전지정 경로, 등록 불가 상품 범위는 제공 문서에서 모두 확인되지 않습니다.

**필수 주장**

- *MA-RP-041-C1** DC·IRP 가입자는 홈페이지 또는 모바일 앱에서 ETF를 직접 매매할 수 있다. 근거: E-DOC53-T10-4ED941F5C6BAFE67 **MA-RP-041-C2** DB 사무담당자용 온라인 서비스에는 상품매수·매도와 부담금 투자비율 변경 기능이 있다. 근거: E-DOC55-TB7-F975DE117DDDBCF5

**문서 근거·주의점**

- *E-DOC53-T10-4ED941F5C6BAFE67** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view?usp=drivesdk) source `doc53` · `#/texts/10` · label `list_item` · variant `delivery` page/slide `1`; charspan `0:45`; bbox `{"b":383.40645349839156,"coord_origin":"BOTTOMLEFT","l":56.04,"r":437.35,"t":393.86198291015626}` retrieval `knowledge-2e34c142aed8-0000` 인용: “DC/IRP 가입자가 당사 홈페이지 or 모바일 App 을 통해 직접 매매 가능” **E-DOC55-TB7-F975DE117DDDBCF5** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/tables/7` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` table cells `r1c5` retrieval `knowledge-a27d15fc4a66-0074` 인용: “상품검색 상품매수.매도 매매내역조회 부담금 투자비율 변경 만기상품예약매수 투자한도초과현황”

**부족 근거·금지 주장**

- *부족 근거** • 개인 IRP의 일반 금융상품 매도·매수 상세 경로 • 향후 입금 부담금의 매수상품 사전지정 경로 • ETF·리츠·ETN·저축은행예금의 사전등록 제한 **금지 주장** • 모든 상품 변경이 동일 화면에서 즉시 처리된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 74. 미래에셋 MA-RP-042 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-042` 검색
- 질문: [퇴직연금] 회사에서 입금해준 퇴직금 입금내역은 어떻게 확인하나요?

**목표 답변**

> DC 온라인 서비스에는 「거래내역조회」와 「부담금입금내역조회」 기능이 있어 회사가 납입한 부담금 내역을 확인할 수 있습니다. 문서에는 DC 입금일 당일 18시 이후 가입자에게 납입결과 알림톡·이메일을 발송한다고도 되어 있습니다. 다만 개인 M-STOCK·홈페이지의 정확한 메뉴 경로는 확인되지 않습니다.

**필수 주장**

- *MA-RP-042-C1** DC 온라인 서비스에는 거래내역조회와 부담금입금내역조회 기능이 있다. 근거: E-DOC55-TB7-7797C5309077967C, E-DOC55-TB7-AABE05D811E80935 **MA-RP-042-C2** DC 부담금 납입결과는 입금일 당일 18시 이후 가입자에게 알림톡과 이메일로 안내된다. 근거: E-DOC55-T220-C7B05BE105007B60, E-DOC55-T221-DB8CEA549B9630F1, E-DOC55-T222-4F799C5A8CF4BB28, E-DOC55-T223-02713195308D540A

**문서 근거·주의점**

- *E-DOC55-TB7-7797C5309077967C** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/tables/7` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` table cells `r2c3` 인용: “거래내역조회” **E-DOC55-TB7-AABE05D811E80935** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/tables/7` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` table cells `r2c4` retrieval `knowledge-a27d15fc4a66-0074` 인용: “부담금입금 신청 부담금입금내역조회 퇴직신청 퇴직신청내역조회 증명서발급” **E-DOC55-T220-C7B05BE105007B60** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/220` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “사무담당자 / 가입자” **E-DOC55-T221-DB8CEA549B9630F1** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/221` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “입금일 당일 18시 이후 부담금 납입결과 알림톡 및” **E-DOC55-T222-4F799C5A8CF4BB28** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/222` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “e-mail” **E-DOC55-T223-02713195308D540A** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/223` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “발송”

**부족 근거·금지 주장**

- *부족 근거** • 개인 M-STOCK·홈페이지의 정확한 거래내역 메뉴 경로 **금지 주장** • 알림 발송만으로 실제 입금·매수 완료를 모두 확정할 수 있다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 75. 미래에셋 MA-RP-043 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-043` 검색
- 질문: [퇴직연금] 퇴직연금 제도가입확인서를 발급 받고 싶습니다. 어떻게 발급 받을 수 있나요?

**목표 답변**

> 사무처리 온라인 서비스의 「증명서 발급」 메뉴에서는 퇴직연금가입확인서를 즉시 발급할 수 있습니다. 다만 개인 M-STOCK의 상세 메뉴, 홈페이지의 정확한 화면 경로, 유선발급 가능 여부는 제공 문서에서 확인되지 않습니다.

**필수 주장**

- *MA-RP-043-C1** 사무처리 온라인 서비스의 증명서 발급 메뉴에서 퇴직연금가입확인서를 즉시 발급할 수 있다. 근거: E-DOC55-T1125-D371F947AEAC05CC, E-DOC55-T1126-D00AA54D0B39166E

**문서 근거·주의점**

- *E-DOC55-T1125-D371F947AEAC05CC** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/1125` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0075` 인용: “『증명서 발급』 메뉴에서는 부담금납입확인서/임금채권보장기금확인서/수수료납입확인서/” **E-DOC55-T1126-D00AA54D0B39166E** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/1126` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0075` 인용: “퇴직연금잔고확인서/퇴직연금가입확인서와 같은 증명서의 즉시 발급도 가능함”

**부족 근거·금지 주장**

- *부족 근거** • 개인 M-STOCK·홈페이지 상세 경로 • 유선 발급 가능 여부 **금지 주장** • 사무담당자용 온라인 서비스와 개인 앱의 발급 경로가 동일하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 76. 미래에셋 MA-RP-046 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-046` 검색
- 질문: [퇴직연금] 중도인출을 신청하였습니다. 언제 받을 수 있나요?

**목표 답변**

> 제공 문서에는 중도인출 신청 후 며칠 이내 지급된다는 고정 기한이 없습니다. 확인되는 절차는 근로자가 사유와 증빙을 준비해 신청하고, 회사가 서류를 확인해 퇴직연금사업자에게 제출한 다음, 사업자가 서류심사·보유상품 매도·퇴직소득세 과세를 거쳐 지급하는 순서입니다. 따라서 회사의 서류 제출과 사업자의 심사·매도 처리가 끝나야 지급되며, 정확한 지급일은 접수 상태와 보유상품 결제일을 확인해야 합니다.

**필수 주장**

- *MA-RP-046-C1** 중도인출은 근로자 신청, 회사 확인·제출, 사업자의 심사·매도·과세·지급 순으로 처리된다. 근거: E-DOC55-T639-94A11079DA972960, E-DOC55-T640-506CB916D8793E7C, E-DOC55-T641-10CCB5189866A079

**문서 근거·주의점**

- *E-DOC55-T639-94A11079DA972960** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/639` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “근로자 : 중도인출사유 확인 및 증빙서류 준비 -> 중도인출신청서 작성 및 제출” **E-DOC55-T640-506CB916D8793E7C** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/640` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “사용자(회사) : 신청서 및 증빙서류 확인 -> 퇴직연금 사업자에 서류제출” **E-DOC55-T641-10CCB5189866A079** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/641` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “퇴직연금 사업자 : 서류심사 -> 고객 보유상품 매도 -> 퇴직소득세 과세 후 가입자 지급”

**부족 근거·금지 주장**

- *부족 근거** • 신청 후 고정 지급기한 • 미래에셋증권의 접수상태별 예상 지급일 • 고객센터 운영시간 **금지 주장** • 서류 신청만 하면 즉시 또는 정해진 영업일에 반드시 지급된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 77. 미래에셋 MA-RP-047 · 부분 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-047` 검색
- 질문: [퇴직연금] 퇴사하였습니다. 퇴직연금은 언제 받을 수 있나요?

**목표 답변**

> 퇴사만으로 즉시 지급되는 것은 아닙니다. DC의 경우 근로자가 퇴직급여신청서와 IRP 가입확인서를 제출하고, 회사가 서류를 확인해 잔여부담금·추가지급금을 DC 계좌에 납입한 뒤 퇴직연금사업자에게 지급을 청구합니다. 이후 사업자가 서류를 심사하고 보유상품을 매도한 다음 세전 퇴직급여를 IRP로 입금합니다. 제공 문서에는 고정 소요일이나 SMS 발송 시점이 없으므로, 지연되면 먼저 회사의 잔여부담금 납입과 서류 제출 여부를 확인해야 합니다.

**필수 주장**

- *MA-RP-047-C1** DC 퇴직급여 지급은 근로자의 신청서·IRP 확인서 제출과 회사의 서류 제출 및 잔여부담금 납입을 거쳐 진행된다. 근거: E-DOC55-T571-0C8669CF96A995E7, E-DOC55-T573-ADCE550031622764, E-DOC55-T574-4E8AB4CA8DF2F1EE, E-DOC55-T575-59E647B557A5C3CD **MA-RP-047-C2** 사업자는 서류 심사와 보유상품 매도 후 세전 퇴직급여를 IRP에 입금한다. 근거: E-DOC55-T577-C9A0742FE98A7535, E-DOC55-T578-6407A7D7DB8E5044

**문서 근거·주의점**

- *E-DOC55-T571-0C8669CF96A995E7** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/571` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “근로자가 퇴직급여신청서를 작성 → IRP 계좌 가입확인서 제출” **E-DOC55-T573-ADCE550031622764** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/573` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “신청한 서류의 내용 확인 → 퇴직급여신청서와 IRP 가입확인서를 퇴직연금사업자에 제출” **E-DOC55-T574-4E8AB4CA8DF2F1EE** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/574` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “부담금 외에 잔여부담금과 추가지급금 등 근로자의 DC 계좌에 납입” **E-DOC55-T575-59E647B557A5C3CD** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/575` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “퇴직연금사업자에게 퇴직금 지급 청구” **E-DOC55-T577-C9A0742FE98A7535** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/577` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “회사가 제출한 서류를 심사 및 접수 → 근로자는 운용하고 있는 금융상품을 매도” **E-DOC55-T578-6407A7D7DB8E5044** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/578` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0043` 인용: “IRP계좌로 세전 퇴직급여 입금”

**부족 근거·금지 주장**

- *부족 근거** • 퇴사 후 고정 지급기한 • 서류접수·지급 SMS 발송 시점 • 연금자산관리센터의 확인 가능 시간 **금지 주장** • 퇴사일만으로 지급일이 자동 확정된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 78. 미래에셋 MA-ISA-001 · 부분 지원

- 섹션: ISA·연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-ISA-001` 검색
- 질문: [ISA] ISA 만기해지 후 연금전환을 하고 싶어요.

**목표 답변**

> ISA 만기자금은 만기 후 60일 안에 연금저축계좌나 IRP로 옮길 수 있고, 전부가 아니라 일부만 이체해도 됩니다. 이 금액은 연금계좌의 연 1,800만원 납입한도와 별도로 입금할 수 있으며, 전환액의 10%를 최대 300만원까지 추가 세액공제 받을 수 있습니다. 다만 제공 문서에는 보유상품을 반드시 먼저 매도해야 하는지, 미래에셋증권에서 어느 채널로 신청하는지까지는 나와 있지 않습니다.

**필수 주장**

- *MA-ISA-001-C1** ISA 만기자금은 만기 후 60일 내 연금저축 또는 IRP로 옮길 수 있다. 근거: E-DOC23-T3-941535FC97BA0C52 **MA-ISA-001-C2** ISA 만기자금은 일부만 이체할 수 있고 연금계좌 연 1,800만원 한도와 별도로 입금할 수 있다. 근거: E-DOC23-T5-E90D17F8E3388D50, E-DOC23-T6-77575F7DB9E1CFE2, E-DOC23-T7-D006A3DBB9E75335 **MA-ISA-001-C3** 연금계좌 전환액의 10%를 최대 300만원까지 추가 세액공제 받을 수 있다. 근거: E-DOC23-T6-EADFF92AA22C7E13

**문서 근거·주의점**

- *E-DOC23-T3-941535FC97BA0C52** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “이렇게 세제혜택을 받은 ISA만기자금은 60일 내에 연금계좌(연금저축, IRP)로 옮길 수 있다.” **E-DOC23-T5-E90D17F8E3388D50** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/5` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “연금계좌의 납입한도는 연 1,800만원이지만 그와 별도로 ISA만기금액은 입금할 수 있다.” **E-DOC23-T6-77575F7DB9E1CFE2** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/6` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “ISA만기자금 중 일부만 연” **E-DOC23-T7-D006A3DBB9E75335** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/7` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “금계좌로 이체할 수도 있는데” **E-DOC23-T6-EADFF92AA22C7E13** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/6` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “계좌에 입금한 금액의 10%를 300만원 한도로 추가 세액공제 혜택을 준다.”

**부족 근거·금지 주장**

- *부족 근거** • 보유상품의 사전 매도·현금화 필요 여부 • 미래에셋증권의 연금전환 신청 채널과 필요서류 • 만기일 산정의 세부 기준 **금지 주장** • 보유상품 평가액을 현물이전할 수 있다는 주장 • 연금자산관리센터에서만 신청 가능하다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

## 5차: 직접 지원 샘플 확인 (13개)

### 79. 한투 PROD-004 · 직접 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-004` 검색
- 질문: IRP 계좌에서 투자할 수 있는 상품에는 어떤 유형이 있나요? 원리금보장형과 비보장형으로 나눠서 설명해주세요

**목표 답변**

> IRP에서는 ETF·펀드·채권 등을 직접 선택해 운용할 수 있습니다. 문서가 100% 투자가능 운용방법으로 분류한 원리금보장 대표 항목은 은행·우체국 예적금, 원리금보장형 보험(GIC), RP이고, 국채·통안채·정부보증채권 등도 포함됩니다. 실적배당상품에는 ETF·펀드 등이 있으며 일반 위험자산 비중은 전체 적립금의 70% 이내입니다. 다만 MMF, 일정 요건의 채권형·채권혼합형 펀드와 TDF처럼 100% 가능할 수 있는 별도 범주가 있으므로 실제 상품별 한도와 현재 판매 여부를 확인해야 합니다.

**필수 주장**

- *C1** IRP에서 ETF·펀드·채권 등을 선택할 수 있고 일반 위험자산은 70% 이내다. 근거: E-IRP-70-D14 **C2** 예적금·GIC·RP·국채와 일부 MMF·펀드·TDF는 문서상 100% 가능 범주에 있다. 근거: E-IRP-SAFE-D58

**문서 근거·주의점**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}` retrieval `knowledge-2fa11c7e5d5c-0006` 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.” **E-IRP-SAFE-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view) `#/tables/0` · label `table` page/slide `1`; charspan `0:0`; bbox `{"b":179.88836669921875,"coord_origin":"BOTTOMLEFT","l":35.43013381958008,"r":557.422119140625,"t":775.9032516479492}` table cells `r1c1, r2c1, r3c1, r4c1, r10c1, r12c1, r13c1` 인용: “은행 및 우체국 예금 / 적금” **E-ETF-LIVE-LIST-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/11` · label `list_item` page/slide `1`; charspan `0:194`; bbox `{"b":293.26645349839157,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.54,"t":365.4019829101563}` 인용: “퇴직연금에서 거래가능한 ETF 는 홈페지지 , MTS(M STOCK) 에서 확인 가능”

**부족 근거·금지 주장**

- *금지 주장** • 정확한 현재 판매 종목이나 티커를 정답에 고정하지 않는다. • 모든 채권과 모든 TDF가 100% 가능하다고 일반화하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 80. 한투 PROD-005 · 직접 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-005` 검색
- 질문: IRP에서 TDF 상품을 매수했는데 위험자산 비율 제한으로 70%만 매수됐습니다. TDF는 위험자산 한도와 무관하게 100% 투자 가능한 상품 아닌가요?

**목표 답변**

> 모든 TDF가 무조건 100% 투자 가능한 것은 아닙니다. 금융감독원장이 정한 요건을 충족한 TDF만 DC·IRP에서 100% 투자할 수 있습니다. 문서상 요건은 목표시점을 설정일 5년 이후로 두고 명칭에 표시할 것, 주식 한도 80% 이내·목표시점 이후 40% 이내, 투자부적격 채권 한도 20% 이내이면서 채무증권 투자액의 50% 이내입니다. 70%만 매수됐다면 해당 상품의 적격 TDF 여부와 상품별 투자한도를 확인해야 합니다.

**필수 주장**

- *C1** 정해진 조건을 충족한 TDF만 DC·IRP에서 100% 투자 가능하다. 근거: E-TDF-100-D53 **C2** 목표시점·주식비중·투자부적격채권 한도 요건이 있다. 근거: E-TDF-CONDITION-1-D53, E-TDF-CONDITION-2-D53, E-TDF-CONDITION-3-D53

**문서 근거·주의점**

- *E-TDF-100-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/16` · label `list_item` page/slide `2`; charspan `0:83`; bbox `{"b":452.68527702780335,"coord_origin":"BOTTOMLEFT","l":74.064,"r":559.4200000000001,"t":480.5979829101563}` retrieval `knowledge-2e34c142aed8-0006` 인용: “금융감독원장이 정한 조건을 충족한 경우 DC 와 IRP 적립금의 100% 투자 가능” **E-TDF-CONDITION-1-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/18` · label `list_item` page/slide `2`; charspan `0:61`; bbox `{"b":361.9452770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":389.9979829101563}` 인용: “투자목표시점을 집합투자기구의 설정일로부터 5 년 이후로 하고” **E-TDF-CONDITION-2-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/19` · label `list_item` page/slide `2`; charspan `0:73`; bbox `{"b":316.5852770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":344.6179829101563}` 인용: “주식의 투자한도를 집합투자기구 자산총액의 80% 이내로 하고” **E-TDF-CONDITION-3-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view) `#/texts/20` · label `list_item` page/slide `2`; charspan `0:72`; bbox `{"b":271.3452770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":299.25798291015633}` 인용: “투자적격등급 이외의 채무증권의 투자한도를 자산총액의 20% 이내로 하고”

**부족 근거·금지 주장**

- *금지 주장** • 모든 TDF가 100% 가능하다고 답하지 않는다. • 상품명이 없는데 해당 TDF가 비적격이라고 확정하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 81. 한투 PROD-009 · 직접 지원

- 섹션: 상품·운용
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `PROD-009` 검색
- 질문: 연금이나 IRP 계좌에서 국내 ETF를 거래하면 일반 계좌보다 세금 혜택이 있나요?

**목표 답변**

> 국내에 상장된 ETF라도 유형별 세금이 다릅니다. 일반계좌에서 국내주식형 ETF는 매매차익이 비과세이고 분배금은 배당소득으로 과세되며, 국내상장 해외 ETF와 그 밖의 ETF는 매매차익과 분배금이 배당소득으로 과세됩니다. 연금계좌에서는 국내주식형 ETF의 분배금, 국내상장 해외 ETF·그 밖의 ETF의 매매차익과 분배금이 인출 전까지 과세이연됩니다. 다만 해외 원천 배당·이자가 있으면 외국납부세액 때문에 과세이연 효과가 낮아질 수 있습니다.

**필수 주장**

- *C1** 일반계좌의 ETF 과세는 국내주식형과 해외주식형·기타 ETF가 다르다. 근거: E-ETF-GENERAL-TAX-D43 **C2** 연금계좌에서는 해당 ETF 수익의 과세가 인출 전까지 이연된다. 근거: E-ETF-PENSION-TAX-D43, E-OVERSEAS-ETF-D42 **C3** 외국납부세액이 있으면 과세이연 효과가 낮아질 수 있다. 근거: E-FOREIGN-DEFERRAL-D36

**문서 근거·주의점**

- *E-ETF-GENERAL-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view) `#/texts/4` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112` 인용: “국내 주식형 월배당 ETF의 매매차익은 비과세, 분배금은 배당소득으로 과세된다.” **E-ETF-PENSION-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view) `#/texts/20` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112` retrieval `knowledge-f146981691bb-0002` 인용: “해외주식형 월배당 ETF와 그 밖의 ETF의 경우 매매차익과 분배금 모두 과세가 이연된다.” **E-OVERSEAS-ETF-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view) `#/texts/15` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185` 인용: “국내 상장 해외 ETF에 투자 시 과세이연효과가 있다.” **E-FOREIGN-DEFERRAL-D36** — [doc36.docx](https://drive.google.com/file/d/1FwipZvxX_ogEbmySP03Tgz7Q7DIBsLfF/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `9647f457ae3130d224642ee23d2284094b33568f2c3bb49542384039b49b6fe1` · Docling JSON SHA-256 `36b46f60be09cb40936a5b90df123ba668356645984b21beb735f737d8d979b0` 인용: “외국납부세액이 발생하는 펀드/ETF 등에 투자한다면 과세이연 효과가 낮아질 수 있다”

**부족 근거·금지 주장**

- *금지 주장** • 모든 국내상장 ETF의 모든 수익에 동일한 세제혜택이 있다고 일반화하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 82. 한투 POLICY-002 · 직접 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-002` 검색
- 질문: 개인연금 수령 개시 시기를 늦추고 싶습니다. 연금 개시는 조건이 되면 자동으로 시작되나요?

**목표 답변**

> 자동으로 지급이 시작되는 것은 아닙니다. 문서상 연금저축의 일반 납입요건은 가입기간 5년 이상이고, 수령은 55세 이후 연간 연금수령한도 안에서 가입자가 수령개시를 신청한 뒤 인출하는 구조입니다. 따라서 조건을 충족해도 신청하지 않으면 개시를 늦출 수 있습니다. 다만 퇴직금 재원 등에는 가입기간 예외가 있을 수 있으므로 계좌 재원을 함께 확인해야 합니다.

**필수 주장**

- *C1** 연금 인출은 55세 이후 가입자의 수령개시 신청 후 이루어진다. 근거: E-PENSION-START-R2

**문서 근거·주의점**

- *E-PENSION-START-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/42` · label `table` page/slide `43`; charspan `0:0`; bbox `{"b":108.07574462890625,"coord_origin":"BOTTOMLEFT","l":55.51258850097656,"r":541.406982421875,"t":636.6895446777344}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1` table cells `r1c1, r2c1` retrieval `prospectus-e66c18ed3f86-0120` 인용: “가입자의 수령개시 신청 후 인출”

**부족 근거·금지 주장**

- *금지 주장** • 나이 도달만으로 자동 지급된다고 말하지 않는다. • 모든 재원에 가입기간 5년을 예외 없이 적용하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 83. 한투 POLICY-003 · 직접 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-003` 검색
- 질문: IRP 계좌에 있는 돈을 출금하고 싶습니다. 어떻게 해야 하나요?

**목표 답변**

> 만 55세 전 IRP 부분 인출은 법에 열거된 사유에 해당할 때만 가능합니다. 문서에 든 사유는 무주택자의 본인 명의 주택 구입, 주거 목적 전세보증금, 가입자나 부양가족의 6개월 이상 요양, 파산·개인회생, 정해진 천재지변 사유 등입니다. 사유에 해당하지 않으면 일반적인 부분 인출은 불가능하고 전체 해지가 필요할 수 있으며, 세금은 계좌 재원과 인출 사유에 따라 달라집니다. 연금 수령 요건을 충족했다면 연금개시 신청 경로도 함께 검토해야 합니다.

**필수 주장**

- *C1** IRP는 법정 사유가 아니면 만 55세 전 중도인출이 불가능하다. 근거: E-IRP-WITHDRAW-D20 **C2** 주택구입·전세보증금·요양·파산·회생·천재지변 등이 법정 사유로 열거된다. 근거: E-IRP-REASONS-D20 **C3** 법정 사유가 아닌 부분 인출은 전체 해지가 필요할 수 있다. 근거: E-IRP-LIQUIDITY-D41

**문서 근거·주의점**

- *E-IRP-WITHDRAW-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view) `#/texts/7` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847` retrieval `knowledge-977c9fc53894-0000` 인용: “중도인출 사유를 법으로 열거하고 있어서, 사유에 해당하지 않으면 만 55세 이전에는 중도인출 자체가 불가능하다.” **E-IRP-REASONS-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view) `#/tables/0` · label `table` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847` table cells `r1c0, r2c0, r3c0, r4c0, r5c0` 인용: “무주택자인 가입자가 본인 명의로 주택 구입” **E-IRP-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view) `#/texts/12` · label `text` 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정 source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0` retrieval `knowledge-40b4f60e717d-0001` 인용: “반면 IRP는 무주택자의 주택 구입 등 법정 사유를 충족해야 부분 인출이 가능해 까다롭다. IRP로만 운용하다 일부 금액이 필요한데 법정사유에 해당되지 않으면 전체를 해지해야 되서 불이익이 크다.” **E-PENSION-START-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/tables/42` · label `table` page/slide `43`; charspan `0:0`; bbox `{"b":108.07574462890625,"coord_origin":"BOTTOMLEFT","l":55.51258850097656,"r":541.406982421875,"t":636.6895446777344}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1` table cells `r1c1, r2c1` retrieval `prospectus-e66c18ed3f86-0120` 인용: “가입자의 수령개시 신청 후 인출”

**부족 근거·금지 주장**

- *금지 주장** • 모든 출금을 같은 세율로 설명하지 않는다. • 법정 사유 확인 없이 부분 인출 가능하다고 답하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 84. 한투 POLICY-006 · 직접 지원

- 섹션: 업무·제도
- 원본 검수본: `hantoo_selected_30.readable.md`에서 `POLICY-006` 검색
- 질문: 연금저축계좌에서 보유 중인 펀드를 매도하고 다른 펀드로 교체하려고 합니다. 이렇게 계좌 내에서 상품을 바꾸면 이미 받은 세액공제가 추징되나요?

**목표 답변**

> 계좌를 유지한 채 연금저축계좌 안에서 펀드 수익증권을 환매하는 시점에는 별도로 과세하지 않습니다. 과세는 연금저축계좌에서 자금을 인출할 때 재원과 수령 방식에 따라 판단됩니다. 따라서 단순한 계좌 내 펀드 매도·교체만으로 이미 받은 세액공제가 곧바로 추징되는 것은 아닙니다. 다만 매도대금을 계좌 밖으로 인출하면 별도의 과세 판단이 필요합니다.

**필수 주장**

- *C1** 연금저축계좌 내 수익증권 환매 시 별도 과세하지 않고 자금 인출 시 과세한다. 근거: E-FUND-SWITCH-TAX-R2

**문서 근거·주의점**

- *E-FUND-SWITCH-TAX-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV) `#/texts/559` · label `list_item` page/slide `43`; charspan `0:154`; bbox `{"b":658.4216083916084,"coord_origin":"BOTTOMLEFT","l":79.56,"r":533.2800000000001,"t":700.22}` Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1` retrieval `prospectus-e66c18ed3f86-0119` 인용: “수익증권을 환매하는 시점에 별도의 과세를 하지 않으며, 연금저축계좌에서 자 금 인출시 다음과 같이 과세”

**부족 근거·금지 주장**

- *금지 주장** • 계좌 내 매도와 계좌 밖 인출을 같은 행위로 취급하지 않는다.

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 85. 미래에셋 MA-PP-003 · 직접 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-003` 검색
- 질문: [개인연금] 연금저축계좌에서 담보대출이 가능한가요?

**목표 답변**

> 가능합니다. 제공 문서상 연금저축(개인연금저축)계좌에 보유한 펀드를 담보로, 융자신청일 기준가 평가금액의 60%까지 신청할 수 있습니다. 연금형 연계 CMA가 필요하고 대출금은 등록된 연계 CMA로 입금됩니다. ETF·리츠·상장인프라펀드와 연계 CMA 예수금은 담보로 인정되지 않습니다. 실제 약정 가능 여부와 적용 금리는 계좌 상태를 기준으로 확인해야 합니다.

**필수 주장**

- *MA-PP-003-C1** 연금저축·개인연금저축계좌의 보유 펀드를 담보로 대출할 수 있다. 근거: E-DOC3-T2-17EFEFE603AB866B **MA-PP-003-C2** 융자신청일 기준가 평가금액의 60%까지 대출할 수 있다. 근거: E-DOC3-T28-2B8B9CCE4136CF82 **MA-PP-003-C3** 연금형 연계 CMA가 필요하고 대출금은 등록된 연계 CMA로 입금된다. 근거: E-DOC3-T12-BD25B0D0DD844A23, E-DOC3-T26-A34F174F28B9E922 **MA-PP-003-C4** ETF·리츠·상장인프라펀드와 연계 CMA 예수금은 담보로 인정되지 않는다. 근거: E-DOC3-T49-A634190ACA6AE989

**문서 근거·주의점**

- *E-DOC3-T2-17EFEFE603AB866B** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view?usp=drivesdk) source `doc3` · `#/texts/2` · label `list_item` · variant `review_local_ocr` page/slide `1`; charspan `0:54`; bbox `{"b":721.3733113606771,"coord_origin":"BOTTOMLEFT","l":54.66666666666667,"r":464.0,"t":736.0399780273438}` 인용: “연금저축계좌 및 개인연금저축계좌 내 보유한 편드틀 담보로 당사에서 지정한 움자비울에 따라 대출실행” **E-DOC3-T28-2B8B9CCE4136CF82** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view?usp=drivesdk) source `doc3` · `#/texts/28` · label `list_item` · variant `review_local_ocr` page/slide `1`; charspan `0:56`; bbox `{"b":43.37331136067712,"coord_origin":"BOTTOMLEFT","l":61.666666666666664,"r":467.6666666666667,"t":58.03997802734375}` 인용: “연금저축(개인연금저축)계좌 내 집합투자증권 전체의 움자신청일 기준가 평가금액의 609 움자 가능” **E-DOC3-T12-BD25B0D0DD844A23** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view?usp=drivesdk) source `doc3` · `#/texts/12` · label `list_item` · variant `review_local_ocr` page/slide `1`; charspan `0:58`; bbox `{"b":455.03997802734375,"coord_origin":"BOTTOMLEFT","l":77.0,"r":359.3333333333333,"t":491.3733113606771}` retrieval `knowledge-243434ee0061-0001` 인용: “연금형 연계CMA계좌 미보유계좌 불가 (연금담보대출계좌와 연금형 연계CMA계좌의 관리부점이 동일해야 함)” **E-DOC3-T26-A34F174F28B9E922** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view?usp=drivesdk) source `doc3` · `#/texts/26` · label `list_item` · variant `review_local_ocr` page/slide `1`; charspan `0:49`; bbox `{"b":86.70664469401038,"coord_origin":"BOTTOMLEFT","l":61.0,"r":414.3333333333333,"t":100.70664469401038}` 인용: “연금저축(개인연금저축)계좌 움자 설정 시 등록된 연금형 연계CMA계좌로 움자금 입금” **E-DOC3-T49-A634190ACA6AE989** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view?usp=drivesdk) source `doc3` · `#/texts/49` · label `list_item` · variant `review_local_ocr` page/slide `2`; charspan `0:106`; bbox `{"b":334.37331136067706,"coord_origin":"BOTTOMLEFT","l":61.66666666666667,"r":539.6666666666667,"t":370.03997802734375}` 인용: “담보유지비율 계산시 연금저축(개인연금저축)계좌의 예수금 집합투자증권만 담보물로 인정되다 연금저축계좌의 ETF, 리초, 상장인프라편드 연금형 연계CMA계좌의 예수금은 담보로 인정되지 않음”

**부족 근거·금지 주장**

- *부족 근거** • 현재 적용 금리 • 고객·계좌별 약정 제한 **금지 주장** • 모든 연금저축계좌가 조건 없이 담보대출 가능 • ETF·리츠·상장인프라펀드도 담보 인정 **검토 메모** • legacy OCR의 '움자/609/리초/편드'는 동일 SHA 원본 PDF와 retrieval 정규화 문구에서 각각 '융자/60%/리츠/펀드'로 확인한 parser drift다. • legacy knowledge bundle: doc3--243434ee0061--docling-local-ocr-v1

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 86. 미래에셋 MA-PP-006 · 직접 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-006` 검색
- 질문: [개인연금] 연금저축계좌에서 ETF를 매 월 정기적으로 자동 매수를 설정할 수 있나요?

**목표 답변**

> 가능합니다. 연금저축계좌의 적립식 자동매수 서비스인 ‘연금 모으기’에서 국내 ETF를 선택하고 투자주기를 매월로 설정할 수 있습니다. M-STOCK의 연금 > 연금 모으기 > 연금 모으기 신청에서 계좌, 투자금액, 투자일자와 기간을 정해 신청합니다.

**필수 주장**

- *MA-PP-006-C1** 연금저축계좌에서 적립식 자동매수 서비스를 신청할 수 있다. 근거: E-DOC9-T75-AC1B17802C4C82EA, E-DOC9-T76-013C94B908DCFC06 **MA-PP-006-C2** 투자주기를 매월로 설정할 수 있다. 근거: E-DOC9-T96-AA679F574490C47F, E-DOC9-T97-344EB7AFAF5CA0D1 **MA-PP-006-C3** 국내 ETF가 적립식 자동매수 주문대상에 포함된다. 근거: E-DOC9-T101-F7C4FB0033FBE063, E-DOC9-TB1-B5E487DB9BBB43E5 **MA-PP-006-C4** M-STOCK의 연금 모으기 신청에서 계좌·투자금액·투자일자와 기간을 정해 신청한다. 근거: E-DOC9-T8-04003E9D13A08DEE, E-DOC9-T69-9193DBFFD9200E13, E-DOC9-T70-7FCFAA1F0D3D2001, E-DOC9-T71-3AA03DC382EAC975

**문서 근거·주의점**

- *E-DOC9-T75-AC1B17802C4C82EA** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/75` · label `section_header` · variant `review_local_ocr` page/slide `5`; charspan `0:57`; bbox `{"b":431.3333333333333,"coord_origin":"BOTTOMLEFT","l":47.0,"r":538.3333333333333,"t":449.0}` 인용: “Q1. 적립식자동매수 서비스 신청올 하니 '위탁거래가능 계좌가 아입니다 ' 라는 오류메시지가 보입니다.” **E-DOC9-T76-013C94B908DCFC06** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/76` · label `list_item` · variant `review_local_ocr` page/slide `5`; charspan `0:79`; bbox `{"b":395.0,"coord_origin":"BOTTOMLEFT","l":73.0,"r":688.0,"t":411.0}` 인용: “연금저축계좌의 경우 적립식 자동매수 신청 전 [3143] 매매거래등록 및 리치/인프라편드매매등록이 모두 '가능' 으로 체크되어 있어야 합니다:” **E-DOC9-T96-AA679F574490C47F** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/96` · label `section_header` · variant `review_local_ocr` page/slide `7`; charspan `0:59`; bbox `{"b":126.0,"coord_origin":"BOTTOMLEFT","l":46.0,"r":557.0,"t":143.33333333333331}` 인용: “08. 투자주기는 매월 1일이고 투자기간을 1년이라고 설정햇올 때 1일이 공휴일인 경우 어떻계 진행되나요?” **E-DOC9-T97-344EB7AFAF5CA0D1** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/97` · label `text` · variant `review_local_ocr` page/slide `7`; charspan `0:74`; bbox `{"b":91.0,"coord_origin":"BOTTOMLEFT","l":73.0,"r":649.6666666666666,"t":107.0}` 인용: “투자일이 비영업일일 때 투자주기가 '매일'인 경우 주문 발주가 없고, '매주 매월'인 경우 최근도래 영업일에 주문 발주가 실행립니다.” **E-DOC9-T101-F7C4FB0033FBE063** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/101` · label `section_header` · variant `review_local_ocr` page/slide `8`; charspan `0:27`; bbox `{"b":285.33333333333337,"coord_origin":"BOTTOMLEFT","l":48.333333333333336,"r":287.33333333333337,"t":302.0}` retrieval `knowledge-614736fd4208-0015` 인용: “Q10. 주문단가와 주문수량은 어떻게 설정되나요?” **E-DOC9-TB1-B5E487DB9BBB43E5** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/tables/1` · label `table` · variant `review_local_ocr` page/slide `8`; charspan `0:0`; bbox `{"b":110.52532958984375,"coord_origin":"BOTTOMLEFT","l":129.2662353515625,"r":650.0624389648438,"t":235.88827514648438}` table cells `r3c0:r4c0` 인용: “국내 ETF” **E-DOC9-T8-04003E9D13A08DEE** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/8` · label `section_header` · variant `review_local_ocr` page/slide `4`; charspan `0:26`; bbox `{"b":433.6666666666667,"coord_origin":"BOTTOMLEFT","l":50.0,"r":248.0,"t":449.6666666666667}` 인용: “1. 연금 > 연금 모으기 > 연금 모으기 신청” **E-DOC9-T69-9193DBFFD9200E13** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/69` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:7`; bbox `{"b":332.33333333333337,"coord_origin":"BOTTOMLEFT","l":579.0,"r":637.0,"t":346.3333333333333}` 인용: “계좌번호 선택” **E-DOC9-T70-7FCFAA1F0D3D2001** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/70` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:7`; bbox `{"b":308.0,"coord_origin":"BOTTOMLEFT","l":579.0,"r":637.0,"t":322.0}` 인용: “투자금액 입력” **E-DOC9-T71-3AA03DC382EAC975** — [doc9.pdf](https://drive.google.com/file/d/1vgtNmFUme4V8P1DeaY2_9bAsuBZwP2Gu/view?usp=drivesdk) source `doc9` · `#/texts/71` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:12`; bbox `{"b":284.0,"coord_origin":"BOTTOMLEFT","l":579.0,"r":669.6666666666666,"t":298.0}` retrieval `knowledge-614736fd4208-0004` 인용: “투자일자 및 기간 설정”

**부족 근거·금지 주장**

- *부족 근거** • 레버리지·인버스 ETF 제외 여부 • 계좌당 포트폴리오 수와 포트폴리오당 종목 수 **금지 주장** • 레버리지·인버스 ETF도 자동매수 가능하다는 주장 • 계좌당 10개 포트폴리오와 포트폴리오당 10종목을 확정하는 주장 **검토 메모** • 원본 p3에는 세부 제한과 10/10이 보이지만 knowledge #/tables/0은 '- - -'로 유실되어 직접 item_ref 근거가 없으므로 답변·claim에서 제외했다. • legacy knowledge bundle: doc9--614736fd4208--docling-local-ocr-v1

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 87. 미래에셋 MA-PP-007 · 직접 지원

- 섹션: 개인연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-PP-007` 검색
- 질문: [개인연금] ISA 계좌가 만기되어 해지했는데 연금저축계좌로 이전이 가능한가요?

**목표 답변**

> 가능합니다. ISA의 의무가입기간 3년을 채운 뒤 만기해지했다면 만기자금을 60일 이내 연금계좌인 연금저축 또는 IRP로 옮길 수 있습니다. 일반 연금계좌 납입한도와 별도로 ISA 만기금액을 넣을 수 있고, 전환액의 10%가 최대 300만원까지 추가 세액공제 대상이 됩니다. 60일 안에 실제 입금까지 완료됐는지 확인하세요.

**필수 주장**

- *MA-PP-007-C1** 의무가입기간 3년을 충족한 ISA 만기자금은 60일 안에 연금저축 또는 IRP로 이전할 수 있다. 근거: E-DOC23-T3-D558B1E481AB051A, E-DOC23-T3-941535FC97BA0C52 **MA-PP-007-C2** ISA 만기금액은 일반 연금계좌 납입한도와 별도로 납입할 수 있고, 전환액의 10%를 최대 300만원까지 추가 세액공제할 수 있다. 근거: E-DOC23-T5-E90D17F8E3388D50, E-DOC23-T6-EADFF92AA22C7E13

**문서 근거·주의점**

- *E-DOC23-T3-D558B1E481AB051A** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “의무가입기간 3년이 지나서 해지하면 만기해지로 인정되서 비과세 · 분리과세 세제혜택을 받을 수 있다.” **E-DOC23-T3-941535FC97BA0C52** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/3` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “이렇게 세제혜택을 받은 ISA만기자금은 60일 내에 연금계좌(연금저축, IRP)로 옮길 수 있다.” **E-DOC23-T5-E90D17F8E3388D50** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/5` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “연금계좌의 납입한도는 연 1,800만원이지만 그와 별도로 ISA만기금액은 입금할 수 있다.” **E-DOC23-T6-EADFF92AA22C7E13** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/texts/6` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` retrieval `knowledge-ba39df5f7ed5-0000` 인용: “계좌에 입금한 금액의 10%를 300만원 한도로 추가 세액공제 혜택을 준다.”

**부족 근거·금지 주장**

- *금지 주장** • 만기 후 60일을 넘겨도 전환 가능 • 전환액과 무관하게 누구나 추가 세액공제 300만원을 전액 받음

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 88. 미래에셋 MA-RP-001 · 직접 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-001` 검색
- 질문: [퇴직연금] 실물이전(현물이전)이 가능하게 되었다는데 어떻게 하면 되나요?

**목표 답변**

> 실물이전은 보유 상품을 매도하지 않고 같은 퇴직연금 제도끼리 금융기관을 바꾸는 방식입니다. DB는 DB로, DC는 DC로, IRP는 IRP로 이전하며, DB·DC는 재직 중인 회사를 통해 신청하고 개인형 IRP는 영업점이나 M-STOCK에서 신청할 수 있습니다. 다만 이전받는 금융기관이 해당 상품을 취급해야 하고 디폴트옵션, 리츠, 사모펀드, RP, MMF 등 제외상품이 있으므로 신청 전에 실물이전 사전조회로 가능 상품을 확인해야 합니다.

**필수 주장**

- *MA-RP-001-C1** 실물이전은 동일 제도 간에 보유 상품을 매도하지 않고 퇴직연금 금융기관을 변경하는 제도이며 DB·DC·IRP는 각각 같은 제도로 이전한다. 근거: E-DOC35-T1-3D6474FAAB7A94E7, E-DOC35-T4-63A106A82653233A, E-DOC35-T5-CBD7A34FFEF3271E, E-DOC35-T6-809F02C5EE426AB7 **MA-RP-001-C2** DB·DC는 재직 중인 회사를 통해 신청하고 IRP는 영업점 또는 M-STOCK에서 신청할 수 있다. 근거: E-DOC35-T8-660F985F352A2A64, E-DOC35-T9-90DECC3099F3F5BA **MA-RP-001-C3** 수관 금융기관이 상품을 취급해야 하며 실물이전 제외상품이 있으므로 사전조회가 필요하다. 근거: E-DOC35-T11-6C93C4A42BD70D63, E-DOC35-T15-AB7B3089CCA5D7D4, E-DOC35-T18-A2763AB5371D6F9B, E-DOC35-T19-C2E8D0316BAA8601, E-DOC35-T21-1B5B6C8EA3A9550B, E-DOC35-T22-254F006E23B54775

**문서 근거·주의점**

- *E-DOC35-T1-3D6474FAAB7A94E7** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/1` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “①동일제도간 보유중인 상품 매도없이 퇴직연금 금융기관을 변경할 수 있는 제도” **E-DOC35-T4-63A106A82653233A** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/4` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “DB제도 → DB제도” **E-DOC35-T5-CBD7A34FFEF3271E** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/5` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “DC제도 → DC제도” **E-DOC35-T6-809F02C5EE426AB7** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/6` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “IRP계좌 → IRP계좌” **E-DOC35-T8-660F985F352A2A64** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/8` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “DB,DC제도는 재직중인 회사를 통해서만 이전 신청 가능” **E-DOC35-T9-90DECC3099F3F5BA** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/9` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “IRP계좌: 영업점을 통한 이전신청, 모바일을 통한 이전신청 가능 (M-STOCK 신청경로 : 연금>타사연금가져오기/실물이전)” **E-DOC35-T11-6C93C4A42BD70D63** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/11` · label `list_item` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “이전하려는 금융기관이 보유중인 상품을 취급하고 있어야 함.” **E-DOC35-T15-AB7B3089CCA5D7D4** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/15` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` retrieval `knowledge-5f307762e3f9-0000` 인용: “디폴트옵션상품, 지분증권, 리츠, 사모펀드, ELF, 파생결합증권, RP, MMF, 종금사 발행어음, 금리연동형보험 등” **E-DOC35-T18-A2763AB5371D6F9B** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/18` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` 인용: “타사로 실제 계약이전을 신청하기 전” **E-DOC35-T19-C2E8D0316BAA8601** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/19` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` 인용: “실물이전 가능한 상품” **E-DOC35-T21-1B5B6C8EA3A9550B** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/21` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` 인용: “미리 확인” **E-DOC35-T22-254F006E23B54775** — [doc35.docx](https://docs.google.com/document/d/1llCZUjrLAFVYSmE2fxrXlCJLf-nXOv0b/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc35` · `#/texts/22` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `5f307762e3f9569841d29791bbc5ac7b130ba8cd40d309d91b74b2c86369f997` · Docling JSON SHA-256 `27b81e9642a594446a6ee4aa1c2fc3186796e5931a72cdbf8de51984d2c5a90d` 인용: “할 수 있는 서비스입니다”

**부족 근거·금지 주장**

- *금지 주장** • DC에서 IRP처럼 다른 제도로 실물이전할 수 있다는 주장 • 모든 보유상품이 그대로 이전된다는 주장 • 사전조회 결과만으로 실제 이전이 반드시 완료된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 89. 미래에셋 MA-RP-005 · 직접 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-005` 검색
- 질문: [퇴직연금]퇴직연금에서 유상청약은 어떻게 하나요?

**목표 답변**

> 퇴직연금 유상청약은 M-STOCK의 연금 > 연금 > 퇴직연금 유상청약에서 대상계좌와 종목을 선택하고, 본청약수량·본배정금액을 확인한 뒤 실제청약가능수량 범위에서 신청합니다. 예약청약과 초과청약은 불가하고 현금으로 본청약만 가능합니다. 투자위험한도 70% 때문에 배정권리가 있어도 청약가능수량이 제한될 수 있습니다. 신주인수권증서는 상장 후 매도만 가능하며, 청약입고일 2영업일 전 권리공매도는 가능합니다.

**필수 주장**

- *MA-RP-005-C1** 퇴직연금 유상청약은 M-STOCK에서 대상계좌와 종목을 선택해 신청한다. 근거: E-DOC24-T5-6A28166FFE50A7EA, E-DOC24-T45-E8ECE87F2E5E4148, E-DOC24-T79-0AFDCC6A6D36F11D **MA-RP-005-C2** 예약청약과 초과청약은 불가하고 현금으로 본청약만 가능하다. 근거: E-DOC24-T99-632439B2AC023C08, E-DOC24-T297-F9DD15187D7A0091 **MA-RP-005-C3** 실제청약가능수량과 투자위험한도 70% 범위에서만 신청할 수 있다. 근거: E-DOC24-T142-93F1BDFA8919EA9D, E-DOC24-T309-CFDE4C2AB9E3BADF **MA-RP-005-C4** 신주인수권증서는 상장 후 매도만 가능하며 청약입고일 2영업일 전 권리공매도가 가능하다. 근거: E-DOC24-T299-E91B3B56DA935592, E-DOC24-T303-E9795D7455A26A9B

**문서 근거·주의점**

- *E-DOC24-T5-6A28166FFE50A7EA** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/5` · label `section_header` · variant `review_local_ocr` page/slide `3`; charspan `0:27`; bbox `{"b":641.3333333333334,"coord_origin":"BOTTOMLEFT","l":22.666666666666668,"r":340.0,"t":665.6666666666666}` 인용: “1) 메뉴 < 연금 < 연금 < 퇴직연금 유상청약” **E-DOC24-T45-E8ECE87F2E5E4148** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/45` · label `list_item` · variant `review_local_ocr` page/slide `4`; charspan `0:41`; bbox `{"b":619.0,"coord_origin":"BOTTOMLEFT","l":45.0,"r":418.6666666666667,"t":638.0}` 인용: “퇴직연금 제도 별 DB, DC가입자 IRP가입자 별 유상청약 대상계좌 선택” **E-DOC24-T79-0AFDCC6A6D36F11D** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/79` · label `list_item` · variant `review_local_ocr` page/slide `5`; charspan `0:42`; bbox `{"b":619.0,"coord_origin":"BOTTOMLEFT","l":44.66666666666667,"r":435.3333333333333,"t":638.0}` retrieval `knowledge-34f64362f828-0002` 인용: “청약기간, 기준일자, 상장종목명, 본청약수량, 본배정금액 확인 후 청약 신청” **E-DOC24-T99-632439B2AC023C08** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/99` · label `text` · variant `review_local_ocr` page/slide `5`; charspan `0:22`; bbox `{"b":287.6666666666667,"coord_origin":"BOTTOMLEFT","l":61.0,"r":202.33333333333334,"t":298.3333333333333}` retrieval `knowledge-34f64362f828-0002` 인용: “퇴직연금 계좌에서는 초과청약이 불가합니다” **E-DOC24-T297-F9DD15187D7A0091** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/297` · label `list_item` · variant `review_local_ocr` page/slide `15`; charspan `0:36`; bbox `{"b":308.6666666666667,"coord_origin":"BOTTOMLEFT","l":47.666666666666664,"r":493.3333333333333,"t":331.0}` retrieval `knowledge-34f64362f828-0013` 인용: “예약청약 및 초과청약은 불가능하고, 현금으로 본청약만 가능합니다.” **E-DOC24-T142-93F1BDFA8919EA9D** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/142` · label `text` · variant `review_local_ocr` page/slide `6`; charspan `0:29`; bbox `{"b":237.66666666666674,"coord_origin":"BOTTOMLEFT","l":313.6666666666667,"r":513.0,"t":278.6666666666667}` 인용: “청약가능금액으로 계산된 실제청약가능수량 범위 내 입력” **E-DOC24-T309-CFDE4C2AB9E3BADF** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/309` · label `list_item` · variant `review_local_ocr` page/slide `16`; charspan `0:56`; bbox `{"b":439.3333333333333,"coord_origin":"BOTTOMLEFT","l":47.333333333333336,"r":495.3333333333333,"t":483.6666666666667}` 인용: “고객의 투자위험한도(70%) 초과로 청약이 어려움 경우, 상품매도 및 입금올 통해서 해소 가능합나다.” **E-DOC24-T299-E91B3B56DA935592** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/299` · label `list_item` · variant `review_local_ocr` page/slide `15`; charspan `0:21`; bbox `{"b":232.66666666666663,"coord_origin":"BOTTOMLEFT","l":47.333333333333336,"r":298.0,"t":254.66666666666663}` retrieval `knowledge-34f64362f828-0014` 인용: “상장 이후 매도만 가능(장외거래 불가)” **E-DOC24-T303-E9795D7455A26A9B** — [doc24.pdf](https://drive.google.com/file/d/1BrkubOOClqr7Tz4PeDdzn37cQ6bEIhRb/view?usp=drivesdk) source `doc24` · `#/texts/303` · label `list_item` · variant `review_local_ocr` page/slide `15`; charspan `0:25`; bbox `{"b":120.66666666666663,"coord_origin":"BOTTOMLEFT","l":47.33333333333333,"r":358.6666666666667,"t":142.0}` 인용: “청약입고일 2영업일 전 권리공매도 가능합나다.”

**부족 근거·금지 주장**

- *부족 근거** • 퇴직연금 유상청약의 내점·유선 신청 가능 여부 **금지 주장** • 별도 연금저축계좌 자료의 초과청약·공매도 규칙을 퇴직연금에 적용 • 내점·유선 신청이 가능하다고 단정 **검토 메모** • 연금저축계좌 자료는 퇴직연금 규칙과 충돌하므로 evidence에서 제외했다. • legacy knowledge bundle: doc24--34f64362f828--docling-local-ocr-v1

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 90. 미래에셋 MA-RP-011 · 직접 지원

- 섹션: 퇴직연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-RP-011` 검색
- 질문: [퇴직연금] 미래에셋증권 퇴직연금 부담금 납입결과 안내 라고 왔는데, 어떤내용인가요?

**목표 답변**

> 퇴직연금 부담금 납입결과 안내는 부담금 입금이 어떻게 처리됐는지를 알려주는 통지입니다. 안내장에는 입금계좌정보, 입금액과 운용지시에 따른 상품매수결과 등이 포함됩니다. DC는 입금일 당일 18시 이후 사무담당자와 가입자에게 알림톡·이메일이 발송되고, DB는 입금일 다음 날 납입결과 알림톡, 상품 매수 완료일 다음 영업일에 담당자 이메일이 발송됩니다.

**필수 주장**

- *MA-RP-011-C1** 부담금 납입결과안내장에는 입금계좌정보, 입금액과 운용지시에 따른 상품매수결과가 포함된다. 근거: E-DOC55-T236-AD0F87FAE7D7826A, E-DOC55-T237-029EC771DC58DA66 **MA-RP-011-C2** DC는 입금일 당일 18시 이후 사무담당자와 가입자에게 납입결과 알림톡과 이메일을 발송한다. 근거: E-DOC55-T218-7ABFFD10CAA6B056, E-DOC55-T220-C7B05BE105007B60, E-DOC55-T221-CFFD034E35D022B9, E-DOC55-T222-4F799C5A8CF4BB28, E-DOC55-T223-02713195308D540A **MA-RP-011-C3** DB는 입금일 다음 날 납입결과 알림톡을 발송하고, 상품 매수 완료일 다음 영업일에 등록된 사무담당자에게 이메일을 발송한다. 근거: E-DOC55-T212-BADEAD3DADA2898D, E-DOC55-T213-1DE68430C1D5B46F, E-DOC55-T214-731BF51CBBF8D52D, E-DOC55-T215-432D2CE859D1E697, E-DOC55-T216-3C94BA33FE9BDB45, E-DOC55-T217-CC8634ED622A2A71

**문서 근거·주의점**

- *E-DOC55-T236-AD0F87FAE7D7826A** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/236` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0014` 인용: “3) 부담금 납입결과안내장” **E-DOC55-T237-029EC771DC58DA66** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/237` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0014` 인용: “- 납입건별 입금결과 (입금계좌정보, 입금액, 운용지시에 따른 상품매수결과 등)” **E-DOC55-T218-7ABFFD10CAA6B056** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/218` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “2) DC” **E-DOC55-T220-C7B05BE105007B60** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/220` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “사무담당자 / 가입자” **E-DOC55-T221-CFFD034E35D022B9** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/221` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “: 입금일 당일 18시 이후 부담금 납입결과 알림톡 및” **E-DOC55-T222-4F799C5A8CF4BB28** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/222` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “e-mail” **E-DOC55-T223-02713195308D540A** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/223` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “발송” **E-DOC55-T212-BADEAD3DADA2898D** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/212` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “- 입금일 익일 부담금 납입결과” **E-DOC55-T213-1DE68430C1D5B46F** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/213` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “알림톡” **E-DOC55-T214-731BF51CBBF8D52D** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/214` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “발송” **E-DOC55-T215-432D2CE859D1E697** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/215` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` retrieval `knowledge-a27d15fc4a66-0012` 인용: “- 부담금 운용지시 상품 매수완료일+1영업일, 등록된 사무담당자” **E-DOC55-T216-3C94BA33FE9BDB45** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/216` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “e-mail로” **E-DOC55-T217-CC8634ED622A2A71** — [doc55.docx](https://docs.google.com/document/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc55` · `#/texts/217` · label `text` · variant `delivery` 페이지 provenance 없음; source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78` 인용: “발송”

**부족 근거·금지 주장**

- *금지 주장** • 안내를 받았다는 사실만으로 모든 상품 매수가 정상 체결됐다고 단정하는 주장 • 모든 제도에서 같은 시각에 발송된다는 주장 • 안내장에 적립금 현황 등 문서에 없는 항목이 반드시 포함된다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영

### 91. 미래에셋 MA-ISA-002 · 직접 지원

- 섹션: ISA·연금
- 원본 검수본: `miraeasset_actual_86.readable.md`에서 `MA-ISA-002` 검색
- 질문: [ISA] ISA가 무엇인가요?

**목표 답변**

> ISA는 한 계좌에서 예금·채권·국내상장주식·펀드·ETF 등을 운용하면서 세제혜택을 받는 개인종합자산관리계좌입니다. 1인 1계좌이고, 19세 이상 국내 거주자 또는 직전 과세기간 근로소득이 있는 15세 이상 거주자가 가입할 수 있습니다. 의무가입기간은 3년이며 납입한도는 연 2,000만원, 누적 최대 1억원입니다. 세제혜택은 일반형 200만원, 서민형 400만원까지 비과세이고 초과분은 9.9% 분리과세됩니다. 직전 3개 과세기간 중 한 번이라도 금융소득종합과세 대상이었다면 가입·만기연장 대상에서 제외됩니다.

**필수 주장**

- *MA-ISA-002-C1** ISA는 1인 1계좌이고 예금·채권·국내상장주식·펀드·ETF 등에 투자할 수 있다. 근거: E-DOC23-TB2-2E97CDD74BB64232, E-DOC23-TB2-48C93476D48A3570 **MA-ISA-002-C2** 가입 대상은 19세 이상 국내 거주자 또는 직전 과세기간 근로소득이 있는 15세 이상 거주자이며, 최근 3개 과세기간 중 금융소득종합과세 대상자는 제외된다. 근거: E-DOC23-TB2-EE277BD38B07554A, E-DOC23-TB2-2B10E6D0184497EE **MA-ISA-002-C3** 의무가입기간은 3년이고 납입한도는 연 2,000만원, 최대 1억원이다. 근거: E-DOC23-TB2-44CFE87A6F5DAE90, E-DOC23-TB2-753A00356CF28005 **MA-ISA-002-C4** 세제혜택은 일반형 200만원·서민형 400만원 비과세와 초과분 9.9% 분리과세다. 근거: E-DOC23-TB2-F2DC7B6B851539F0

**문서 근거·주의점**

- *E-DOC23-TB2-2E97CDD74BB64232** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r1c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “1인 1개 보유 (만기연장/재가입 가능)” **E-DOC23-TB2-48C93476D48A3570** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r4c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “예금, 채권, 국내상장주식, 펀드, ETF 등” **E-DOC23-TB2-EE277BD38B07554A** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r2c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “19세 이상 국내 거주자, 농어민 직전 과세기간 근로소득 있는 15세 이상 거주자” **E-DOC23-TB2-2B10E6D0184497EE** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r3c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “직전 3개 과세기간 중 1회 이상 금융소득종합과세 해당되면 제외” **E-DOC23-TB2-44CFE87A6F5DAE90** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r6c2` 인용: “3년” **E-DOC23-TB2-753A00356CF28005** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r7c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “연 2,000만원(최대 1억) 이월 납입 가능” **E-DOC23-TB2-F2DC7B6B851539F0** — [doc23.docx](https://docs.google.com/document/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/edit?usp=drivesdk&ouid=112966981495050116961&rtpof=true&sd=true) source `doc23` · `#/tables/2` · label `table` · variant `delivery` 페이지 provenance 없음; source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235` table cells `r5c2` retrieval `knowledge-ba39df5f7ed5-0007` 인용: “200만원(서민형 400만원) 비과세 초과 금액 9.9% 분리과세 (종합과세 대상 아님) ”

**부족 근거·금지 주장**

- *금지 주장** • ISA 가입자 누구나 400만원 비과세라는 주장 • 금융소득종합과세 대상자도 제한 없이 신규 가입할 수 있다는 주장

**사람 검수 결과**

- 판정: [ ] OK  [ ] 수정 필요  [ ] 보류
- 확인: [ ] 질문 의도  [ ] 목표 답변  [ ] 필수 주장  [ ] 부족 근거·금지 주장
- 수정 메모:
- 최종 반영 여부: [ ] 반영 완료  [ ] 반영 불필요  [ ] 미반영
