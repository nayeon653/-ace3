# PR #128 한투 30문항 Gold Answer 쉬운 검수본

원본 표가 너무 넓어 문항별 카드 형태로 다시 펼친 검수용 문서입니다. 정본은 `hantoo_selected_30.table.md`입니다.

## 빠른 요약

- 전체 문항: 30개
- 상품·운용: 15개
- 업무·제도: 15개
- 근거충분도(원본): 부분 지원 15개, 미지원 5개, 직접 지원 9개, 최신성 공백 1개
- 근거충분도(사람 검수 반영 후): 부분 지원 16개, 미지원 5개, 직접 지원 8개, 최신성 공백 1개 (PROD-004를 직접 지원→부분 지원으로 재분류)

## 검수 방법

- 각 문항은 질문, 목표 답변, 필수 주장, 문서 근거, 부족 근거·금지 주장 순서로 펼쳤습니다.
- `근거충분도`가 `미지원` 또는 `부분 지원`이면 답변 가능 범위와 금지 주장을 먼저 확인하세요.
- 문서 근거가 `no page/slide provenance`로 표시된 문항은 원문 위치 추적이 약한 항목입니다.

## 상품·운용 (15개)

### PROD-001 · 부분 지원

**질문**

> IRP 계좌에 현금성 자산이 있는데 이걸 펀드로 투자하려니 실제 매수 가능 금액이 훨씬 적게 나옵니다. 왜 그런가요?

**목표 답변**

> 펀드라고 해서 모두 위험자산으로 분류되는 것은 아니므로, 현재 정보만으로 실제 매수 가능 금액이 적게 표시되는 정확한 원인을 확정하기는 어렵습니다. 매수하려는 펀드가 위험자산으로 분류되는 경우에는 IRP의 위험자산 투자 비중이 전체 적립금의 70% 이내로 제한되므로, 현금성자산이 충분하더라도 남아 있는 위험자산 한도까지만 매수할 수 있습니다. 반면 해당 펀드가 비위험자산이라면 이 70% 제한만으로는 매수 가능 금액이 적은 이유를 설명할 수 없습니다. 정확한 원인을 확인하려면 해당 펀드의 위험자산 분류, 현재 위험자산 보유비중 및 계좌의 매수가능액 산정 내역을 확인해야 합니다.

**필수 주장**

- *C1·DIRECT** IRP의 위험자산 투자 비중은 전체 적립금의 70% 이내다.
- 근거: E-IRP-70-D14, E-IRP-70-D58
- *필수 응답 행동**
- • 매수하려는 펀드가 위험자산이라고 단정하지 않는다.
- • 위험자산으로 분류되는 경우에만 70% 제한을 가능한 원인으로 제시한다.
- • 비위험자산이라면 70% 제한으로 설명할 수 없다고 구분한다.
- • 현재 자료만으로 실제 계좌의 정확한 원인은 확정하지 않는다.

**문서 근거 요약**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}`
- retrieval `knowledge-2fa11c7e5d5c-0006`
- 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”
- *E-IRP-70-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view)
- `#/texts/1` · label `section_header`
- page/slide `2`; charspan `0:28`; bbox `{"b":788.6752770278034,"coord_origin":"BOTTOMLEFT","l":36.0,"r":324.53,"t":800.0399829101564}`
- 인용: “퇴직연금 적립금의 70% 까지만 투자가능한 운용방법”

**부족 근거·금지 주장**

- *부족 근거**
- • 개별 계좌의 현재 위험자산 비중, 주문가능금액 산식과 대상 펀드 분류가 없다.
- *금지 주장**
- • 70% 한도가 유일한 원인이라고 단정하지 않는다.
- • 현금성자산의 30%가 항상 매수가능하다고 계산하지 않는다.
- • 매수하려는 펀드가 위험자산이라고 단정하지 않는다.
- *검토 메모**
- • 질문에는 매수 대상 펀드의 위험자산 분류가 제시되지 않았으므로 70% 제한은 조건부 가능성으로만 제시한다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-002 · 미지원

**질문**

> 연금저축펀드 계좌에서는 위험자산 편입 비율에 제한이 있나요?

**목표 답변**

> 제공된 문서 집합만으로는 연금저축펀드 계좌의 위험자산 총량 제한 유무를 직접 확인할 수 없습니다. 매우 높은 위험(1등급) 상품에 연금저축계좌로 매입 가능한 클래스가 있다는 점은 확인되지만, 이것만으로 계좌 전체의 위험자산 한도가 없다고 단정할 수는 없습니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거 요약**

- *E-HIGH-RISK-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/0` · label `text`
- page/slide `1`; charspan `0:118`; bbox `{"b":749.9090909090909,"coord_origin":"BOTTOMLEFT","l":247.0,"r":566.7969999999999,"t":798.0}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1`
- 인용: “실제 수익률 변동성을 감안 하여 1등급으로 분류하였습니다.”
- *E-PENSION-CLASS-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/7` · label `table`
- page/slide `7`; charspan `0:0`; bbox `{"b":394.6044006347656,"coord_origin":"BOTTOMLEFT","l":71.91475677490234,"r":575.2330322265625,"t":779.9194984436035}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1`
- table cells `r5c1` 
- 인용: “연금저축계좌를 통해 매입이 가능한 집합투자기구입니다.”

**부족 근거·금지 주장**

- *부족 근거**
- • ‘연금저축 위험자산 비율 제한 없음’을 직접 명시한 제공 문서 근거가 없다.
- *금지 주장**
- • 고위험 상품 클래스의 존재만으로 계좌 총량 제한 부재를 추론하지 않는다.
- *필수 응답 행동**
- • 위험자산 총량 제한 유무를 제공 문서로 확정할 수 없다고 밝힌다.
- • 개별 1등급 상품의 매입 가능 사례를 계좌 전체의 한도 부재로 확대해석하지 않는다.
- *검토 메모**
- • OK. 현재 `미지원` 유지가 적절하다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-003 · 부분 지원

**질문**

> IRP 계좌에서 국채 ETF를 보유 중인데 평가금액이 계속 줄어듭니다. 국채 ETF는 어떤 상품인가요?

**목표 답변**

> ETF는 지수형 펀드의 성격과 거래소에서 실시간 거래되는 성격을 함께 갖습니다. 국채를 담은 ETF도 시장가격이 변하는 실적배당상품이며, 문서상 채권은 시장금리가 오르면 가격이 내려가 원금손실이 날 수 있습니다. 잔존만기가 긴 채권일수록 금리변동의 영향이 큰 경향도 있습니다. 따라서 평가금액 하락은 금리와 기초채권 가격 변화에 관련될 수 있지만, 보유 종목과 매수시점 정보 없이 정확한 하락 원인을 특정할 수는 없습니다.

**필수 주장**

- *C1** ETF는 인덱스 펀드와 거래소 실시간 거래의 성격을 함께 가진다.
- 근거: E-ETF-STRUCTURE-D53
- *C2** 금리 상승은 채권가치 하락과 원금손실 가능성을 만든다.
- 근거: E-BOND-RATE-R2B
- *C3** 잔존만기가 긴 채권은 금리변동 영향을 더 크게 받는 경향이 있다.
- 근거: E-BOND-DURATION-R2C

**문서 근거 요약**

- *E-ETF-STRUCTURE-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/8` · label `list_item`
- page/slide `1`; charspan `0:74`; bbox `{"b":461.0464534983916,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.5385599999998,"t":492.1419829101563}`
- 인용: “인덱스 펀드의 장점과 거래소에 상장되어 실시간으 로 거래되는 주식의 장점을 모두 갖춘 펀드”
- *E-BOND-RATE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/43` · label `table`
- page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- table cells `r3c1`
- 인용: “시장이자율이 상승하는 경우 채권가격을 결정하는 할인율이 함께 상승함에 따라 그 가치가 하락”
- *E-BOND-DURATION-R2C** — [R2_KR5144420020.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/6` · label `table`
- page/slide `7`; charspan `0:0`; bbox `{"b":64.49822998046875,"coord_origin":"BOTTOMLEFT","l":48.67829513549805,"r":555.131591796875,"t":788.495174407959}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5144420020--f65b36a28194--docling-no-ocr-native-v1`
- table cells `r4c2`
- 인용: “잔존만기가 긴 장기채권은 단기채권보다 금리에 영향을 많이 받으며”

**부족 근거·금지 주장**

- *부족 근거**
- • 고객 보유 ETF의 종목, 듀레이션, 매수시점과 실제 가격 경로가 없다.
- *금지 주장**
- • 평가손실의 원인을 금리 하나로 확정하지 않는다.
- • 국채 ETF를 원금보장상품으로 표현하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-004 · 부분 지원 (기존: 직접 지원)

**질문**

> IRP 계좌에서 투자할 수 있는 상품에는 어떤 유형이 있나요? 원리금보장형과 비보장형으로 나눠서 설명해주세요

**목표 답변**

> IRP에서는 ETF·펀드·채권 등을 직접 선택해 운용할 수 있고, 일반 위험자산 비중은 전체 적립금의 70% 이내로 제한됩니다. 문서상 원리금보장형 운용방법 표에는 은행 및 우체국 예금·적금이 100% 투자가능 항목으로 포함되어 있고, 이 밖에도 여러 행이 있어 다른 원리금보장 상품이나 일부 조건부 실적배당상품(MMF, 요건을 충족한 채권형·TDF 등)이 함께 포함되어 있을 가능성이 있습니다. 다만 제공 자료에서는 그 표의 각 행에 어떤 상품명이 적혀 있는지 전부 확인되지 않으므로, GIC·RP·국채 등 구체적인 상품명까지 단정할 수는 없습니다. 정확한 원리금보장·실적배당 상품 목록과 현재 판매 여부는 회사의 최신 상품안내에서 확인해야 합니다.

**필수 주장**

- *C1** IRP에서 ETF·펀드·채권 등을 선택할 수 있고 일반 위험자산은 70% 이내다.
- 근거: E-IRP-70-D14
- *C2** 원리금보장형 운용방법 표에는 은행 및 우체국 예금·적금이 100% 투자가능 항목으로 포함되고, 표에는 이 밖에도 여러 행이 있다.
- 근거: E-IRP-SAFE-D58

**문서 근거 요약**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}`
- retrieval `knowledge-2fa11c7e5d5c-0006`
- 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”
- *E-IRP-SAFE-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view)
- `#/tables/0` · label `table`
- page/slide `1`; charspan `0:0`; bbox `{"b":179.88836669921875,"coord_origin":"BOTTOMLEFT","l":35.43013381958008,"r":557.422119140625,"t":775.9032516479492}`
- table cells `r1c1, r2c1, r3c1, r4c1, r10c1, r12c1, r13c1`
- 인용: “은행 및 우체국 예금 / 적금”
- *E-ETF-LIVE-LIST-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/11` · label `list_item`
- page/slide `1`; charspan `0:194`; bbox `{"b":293.26645349839157,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.54,"t":365.4019829101563}`
- 인용: “퇴직연금에서 거래가능한 ETF 는 홈페지지 , MTS(M STOCK) 에서 확인 가능”

**부족 근거·금지 주장**

- *부족 근거**
- • E-IRP-SAFE-D58 표의 r2~r13 행에 실제로 어떤 상품명(GIC, RP, 국채·통안채·정부보증채권, MMF, 채권형·채권혼합형 펀드, TDF 등)이 적혀 있는지 인용문으로 확인되지 않는다.
- *금지 주장**
- • 정확한 현재 판매 종목이나 티커를 정답에 고정하지 않는다.
- • 모든 채권과 모든 TDF가 100% 가능하다고 일반화하지 않는다.
- • 표에 GIC·RP·국채·통안채·정부보증채권·MMF·채권형펀드·TDF가 포함되어 있다고 구체적으로 단정하지 않는다.
- *검토 메모**
- • 사람 검수 결과(수정 필요 → 수정 후 반영): 기존 목표 답변과 C2가 GIC·RP·국채·통안채·정부보증채권·MMF·채권형혼합형펀드·TDF를 구체적으로 나열했으나, 근거 요약과 정본(table.md) 모두 표 셀 텍스트는 "은행 및 우체국 예금/적금" 하나만 인용되어 있고 나머지 6개 행(r2, r3, r4, r10, r12, r13)의 실제 텍스트는 제공되지 않음. 표 일부 행만 확인됐는데 나머지 상품까지 열거한 원칙 2 위반(및 원칙 1 위반)으로 판단해, 확인된 항목만 남기고 나머지는 "확인되지 않는다"로 명시함. 근거충분도도 확대 열거를 제거하면 "직접 지원"을 유지하기 어려워 "부분 지원"으로 하향함.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 최종 반영 여부: [ ] 반영 불필요  [x] 수정 후 반영  [ ] 원문 확인 전 미반영

### PROD-005 · 직접 지원

**질문**

> IRP에서 TDF 상품을 매수했는데 위험자산 비율 제한으로 70%만 매수됐습니다. TDF는 위험자산 한도와 무관하게 100% 투자 가능한 상품 아닌가요?

**목표 답변**

> 모든 TDF가 무조건 100% 투자 가능한 것은 아닙니다. 금융감독원장이 정한 요건을 충족한 TDF만 DC·IRP에서 100% 투자할 수 있습니다. 문서상 요건은 목표시점을 설정일 5년 이후로 두고 명칭에 표시할 것, 주식 한도 80% 이내·목표시점 이후 40% 이내, 투자부적격 채권 한도 20% 이내이면서 채무증권 투자액의 50% 이내입니다. 70%만 매수됐다면 해당 상품의 적격 TDF 여부와 상품별 투자한도를 확인해야 합니다.

**필수 주장**

- *C1** 정해진 조건을 충족한 TDF만 DC·IRP에서 100% 투자 가능하다.
- 근거: E-TDF-100-D53
- *C2** 목표시점·주식비중·투자부적격채권 한도 요건이 있다.
- 근거: E-TDF-CONDITION-1-D53, E-TDF-CONDITION-2-D53, E-TDF-CONDITION-3-D53

**문서 근거 요약**

- *E-TDF-100-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/16` · label `list_item`
- page/slide `2`; charspan `0:83`; bbox `{"b":452.68527702780335,"coord_origin":"BOTTOMLEFT","l":74.064,"r":559.4200000000001,"t":480.5979829101563}`
- retrieval `knowledge-2e34c142aed8-0006`
- 인용: “금융감독원장이 정한 조건을 충족한 경우 DC 와 IRP 적립금의 100% 투자 가능”
- *E-TDF-CONDITION-1-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/18` · label `list_item`
- page/slide `2`; charspan `0:61`; bbox `{"b":361.9452770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":389.9979829101563}`
- 인용: “투자목표시점을 집합투자기구의 설정일로부터 5 년 이후로 하고”
- *E-TDF-CONDITION-2-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/19` · label `list_item`
- page/slide `2`; charspan `0:73`; bbox `{"b":316.5852770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":344.6179829101563}`
- 인용: “주식의 투자한도를 집합투자기구 자산총액의 80% 이내로 하고”
- *E-TDF-CONDITION-3-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:72`; bbox `{"b":271.3452770278034,"coord_origin":"BOTTOMLEFT","l":92.064,"r":559.4200000000001,"t":299.25798291015633}`
- 인용: “투자적격등급 이외의 채무증권의 투자한도를 자산총액의 20% 이내로 하고”

**부족 근거·금지 주장**

- *금지 주장**
- • 모든 TDF가 100% 가능하다고 답하지 않는다.
- • 상품명이 없는데 해당 TDF가 비적격이라고 확정하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-006 · 부분 지원

**질문**

> 연금저축계좌와 IRP계좌는 투자할 수 있는 상품이나 투자비율 제한이 어떻게 다른가요?

**목표 답변**

> IRP는 ETF·펀드·채권 등을 운용할 수 있고 일반 위험자산은 전체 적립금의 70% 이내라는 점이 문서에서 확인됩니다. 연금저축은 매우 높은 위험 등급의 연금저축용 펀드 클래스가 실제로 존재한다는 점까지 확인됩니다. 그러나 제공 문서에는 연금저축의 전체 투자가능 상품군과 위험자산 총량 제한 유무를 직접 명시한 비교 규정이 없어 그 차이까지 단정한 완전 비교는 할 수 없습니다.

**필수 주장**

- *C1** IRP는 ETF·펀드·채권 등을 운용하며 일반 위험자산은 70% 이내다.
- 근거: E-IRP-70-D14
- *C2** 1등급 상품에 연금저축계좌 매입 가능 클래스가 존재한다.
- 근거: E-HIGH-RISK-R2A, E-PENSION-CLASS-R2A

**문서 근거 요약**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}`
- retrieval `knowledge-2fa11c7e5d5c-0006`
- 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”
- *E-HIGH-RISK-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/0` · label `text`
- page/slide `1`; charspan `0:118`; bbox `{"b":749.9090909090909,"coord_origin":"BOTTOMLEFT","l":247.0,"r":566.7969999999999,"t":798.0}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1`
- 인용: “실제 수익률 변동성을 감안 하여 1등급으로 분류하였습니다.”
- *E-PENSION-CLASS-R2A** — [R2_KR5153450772.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/7` · label `table`
- page/slide `7`; charspan `0:0`; bbox `{"b":394.6044006347656,"coord_origin":"BOTTOMLEFT","l":71.91475677490234,"r":575.2330322265625,"t":779.9194984436035}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450772--fb3b7a864751--docling-no-ocr-native-v1`
- table cells `r5c1`
- 인용: “연금저축계좌를 통해 매입이 가능한 집합투자기구입니다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 연금저축 전체 상품군과 계좌 수준 위험자산 총량 규정이 없다.
- *금지 주장**
- • 연금저축에는 위험자산 제한이 없다고 단정하지 않는다.
- • 고위험 클래스 하나를 전체 상품군으로 일반화하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-007 · 부분 지원

**질문**

> 연금저축, IRP, 퇴직연금(DC) 계좌 중 어느 계좌가 담보대출이 가능한가요?

**목표 답변**

> 문서에서 직접 확인되는 것은 해당 회사의 연금저축·개인연금저축계좌 증권담보융자입니다. 계좌 안의 보유 펀드를 담보로 회사가 정한 융자비율에 따라 대출하며, 해당 연금저축계좌의 약정 가능도 명시합니다. 반면 IRP·DC 자료에는 기존 담보대출 원리금 상환을 위한 중도인출 맥락만 있어 신규 담보대출 가능 또는 불가를 직접 정하지 않습니다. 따라서 연금저축은 이 회사 문서 기준으로 가능하다고 답할 수 있지만, IRP·DC와 다른 금융회사의 최신 취급 여부는 별도 확인해야 합니다.

**필수 주장**

- *C1** 해당 회사 문서상 연금저축·개인연금저축계좌의 보유 펀드를 담보로 대출할 수 있다.
- 근거: E-PENSION-COLLATERAL-D3, E-PENSION-COLLATERAL-ELIGIBLE-D3

**문서 근거 요약**

- *E-PENSION-COLLATERAL-D3** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view)
- `#/texts/2` · label `list_item`
- page/slide `1`; charspan `0:54`; bbox `{"b":721.3733113606771,"coord_origin":"BOTTOMLEFT","l":54.66666666666667,"r":464.0,"t":736.0399780273438}`
- retrieval `knowledge-243434ee0061-0000`
- 인용: “연금저축계좌 및 개인연금저축계좌 내 보유한 편드틀 담보로 당사에서 지정한 움자비울에 따라 대출실행”
- *E-PENSION-COLLATERAL-ELIGIBLE-D3** — [doc3.pdf](https://drive.google.com/file/d/1y-Y5cmtnY8PinMLiSczqzA88o7yuDjx2/view)
- `#/texts/7` · label `list_item`
- page/slide `1`; charspan `0:26`; bbox `{"b":584.0399780273438,"coord_origin":"BOTTOMLEFT","l":53.0,"r":238.33333333333334,"t":598.7066446940104}`
- retrieval `knowledge-243434ee0061-0001`
- 인용: “당사 연금저축(개인연금저축)계좌 약정 가능”
- *E-COLLATERAL-CONTEXT-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view)
- `#/tables/0` · label `table`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847`
- table cells `r6c0`
- 인용: “퇴직연금제도를 받을 권리를 담보로 제공하고 대출받은 가입자가 그 대출 원리금을 상환하기 위한 경우”
- *E-COLLATERAL-CONTEXT-D55** — [doc55.docx](https://drive.google.com/file/d/1cyx2csXf2gIwv3XgJwfmDMsgSji25ykq/view)
- `#/texts/383` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `a27d15fc4a66d42dca863bbe3cdcbbab09852ffe034af71e52ec6338b6b5233d` · Docling JSON SHA-256 `9647dd1411286223ef38fdfd904d99693491185daec43d5ef2f90a67c6672b78`
- 인용: “퇴직연금(DB/DC) 적립금을 담보로 대출받은 금액을 상환”

**부족 근거·금지 주장**

- *부족 근거**
- • IRP·DC의 신규 담보대출 가능·불가와 금융회사별 최신 취급 여부를 직접 정한 항목이 없다.
- • 최종 배포 no-OCR 번들에서는 doc3 본문이 탈락해 로컬 OCR Docling 객체·원본 PDF 렌더·검색 청크를 교차검증했다.
- *금지 주장**
- • 상환 사유의 존재를 IRP·DC의 신규 담보대출 가능성으로 바꾸어 말하지 않는다.
- • 한 회사의 연금저축 취급 문서를 전 금융회사에 일반화하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-008 · 미지원

**질문**

> 금 실물을 직접 사는 것과 금 ETF에 투자하는 것은 어떤 차이가 있고, 어느 쪽이 유리한가요?

**목표 답변**

> 제공된 문서에서는 금 실물과 금 ETF의 상품 구조, 실물 인출 방식, 비용 및 과세 차이를 확인할 수 없습니다. 따라서 현재 확인 가능한 자료만으로 두 투자 방식의 차이를 구체적으로 비교하거나 어느 쪽이 더 유리하다고 판단하기는 어렵습니다. 정확한 비교를 위해서는 각 상품의 거래 방식, 비용 및 과세 기준을 확인할 수 있는 추가 자료가 필요합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거 요약**

- 직접 근거 없음

**부족 근거·금지 주장**

- *부족 근거**
- • 금 실물과 금 ETF의 상품 구조 및 과세 근거가 전부 없다.
- *금지 주장**
- • 외부 세법 지식으로 빈 근거를 채우지 않는다.
- • ‘골드플랜’ 펀드명을 금 투자 근거로 오인하지 않는다.
- • 어느 쪽이 더 유리하다고 추천하거나 단정하지 않는다.
- *필수 응답 행동**
- • 금 실물과 금 ETF의 구조, 세금, 수수료, 실물 인출 가능 여부, 투자 유불리를 제공 문서만으로 확정할 수 없다고 밝힌다.
- • 관련 없는 상품명을 금 실물·금 ETF 비교 근거로 사용하지 않는다.
- *검토 메모**
- • 미지원 판정은 적절하나, 내부 평가 용어를 사용자 대상 표현으로 수정했다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-009 · 직접 지원

**질문**

> 연금이나 IRP 계좌에서 국내 ETF를 거래하면 일반 계좌보다 세금 혜택이 있나요?

**목표 답변**

> 국내에 상장된 ETF라도 유형별 세금이 다릅니다. 일반계좌에서 국내주식형 ETF는 매매차익이 비과세이고 분배금은 배당소득으로 과세되며, 국내상장 해외 ETF와 그 밖의 ETF는 매매차익과 분배금이 배당소득으로 과세됩니다. 연금계좌에서는 국내주식형 ETF의 분배금, 국내상장 해외 ETF·그 밖의 ETF의 매매차익과 분배금이 인출 전까지 과세이연됩니다. 다만 해외 원천 배당·이자가 있으면 외국납부세액 때문에 과세이연 효과가 낮아질 수 있습니다.

**필수 주장**

- *C1** 일반계좌의 ETF 과세는 국내주식형과 해외주식형·기타 ETF가 다르다.
- 근거: E-ETF-GENERAL-TAX-D43
- *C2** 연금계좌에서는 해당 ETF 수익의 과세가 인출 전까지 이연된다.
- 근거: E-ETF-PENSION-TAX-D43, E-OVERSEAS-ETF-D42
- *C3** 외국납부세액이 있으면 과세이연 효과가 낮아질 수 있다.
- 근거: E-FOREIGN-DEFERRAL-D36

**문서 근거 요약**

- *E-ETF-GENERAL-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view)
- `#/texts/4` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112`
- 인용: “국내 주식형 월배당 ETF의 매매차익은 비과세, 분배금은 배당소득으로 과세된다.”
- *E-ETF-PENSION-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view)
- `#/texts/20` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112`
- retrieval `knowledge-f146981691bb-0002`
- 인용: “해외주식형 월배당 ETF와 그 밖의 ETF의 경우 매매차익과 분배금 모두 과세가 이연된다.”
- *E-OVERSEAS-ETF-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view)
- `#/texts/15` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185`
- 인용: “국내 상장 해외 ETF에 투자 시 과세이연효과가 있다.”
- *E-FOREIGN-DEFERRAL-D36** — [doc36.docx](https://drive.google.com/file/d/1FwipZvxX_ogEbmySP03Tgz7Q7DIBsLfF/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `9647f457ae3130d224642ee23d2284094b33568f2c3bb49542384039b49b6fe1` · Docling JSON SHA-256 `36b46f60be09cb40936a5b90df123ba668356645984b21beb735f737d8d979b0`
- 인용: “외국납부세액이 발생하는 펀드/ETF 등에 투자한다면 과세이연 효과가 낮아질 수 있다”

**부족 근거·금지 주장**

- *금지 주장**
- • 모든 국내상장 ETF의 모든 수익에 동일한 세제혜택이 있다고 일반화하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-010 · 부분 지원

**질문**

> 퇴직을 앞두고 있고 퇴직금이 크게 들어올 예정입니다. IRP 계좌에서 매년 일정 수익률을 목표로 포트폴리오를 어떻게 구성하면 좋을까요?

**목표 답변**

> 매년 일정한 수익률을 달성하도록 보장되는 포트폴리오는 제시하기 어렵습니다. 구체적인 비중은 투자경력과 투자성향, 투자기간, 필요한 현금흐름과 감내 가능한 손실 수준을 확인한 후 정해야 합니다. IRP의 일반 위험자산 비중은 전체 적립금의 70% 이내로 제한되지만, 이는 최대한도일 뿐 70% 편입을 권장한다는 의미는 아닙니다. 제공 문서에는 고객별 권장 비중과 구체적인 상품 조합을 정할 근거가 없습니다.

**필수 주장**

- *C1** 성과목표는 반드시 실현된다고 보장되지 않는다.
- 근거: E-NO-GUARANTEE-R2B
- *C2** 상품이 투자경력과 투자성향에 적합한지 확인해야 한다.
- 근거: E-SUITABILITY-R2B
- *C3** IRP 위험자산 투자 비중은 전체 적립금의 70% 이내다.
- 근거: E-IRP-70-D14

**문서 근거 요약**

- *E-NO-GUARANTEE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/33` · label `list_item`
- page/slide `2`; charspan `0:97`; bbox `{"b":575.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":524.3420000000001,"t":598.0}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- 인용: “성과목표는 반드시 실현된다는 보장은 없습니다.”
- *E-SUITABILITY-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/32` · label `list_item`
- page/slide `2`; charspan `0:95`; bbox `{"b":631.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":525.676,"t":654.0}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- 인용: “투 자경력이나 투자성향에 적합한 상품인지 신중한 투자결정을 하시기 바랍니다.”
- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}`
- retrieval `knowledge-2fa11c7e5d5c-0006`
- 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 투자기간, 위험성향, 현금흐름과 고객별 손실 감내수준이 없다.
- • 과거 실적이 미래 성과를 보장하지 않는다는 문장은 현재 연결된 인용문으로 직접 확인되지 않는다.
- • 고객별 권장 비중과 구체적인 상품 조합을 정할 근거가 없다.
- *금지 주장**
- • 목표수익률 달성을 보장하지 않는다.
- • 고객 정보 없이 구체적 비중이나 종목을 추천하지 않는다.
- • 위험자산 70% 한도를 권장 비중처럼 말하지 않는다.
- *검토 메모**
- • 현재 목표 답변은 성과 보장 불가와 70% 한도만 강조하여 포트폴리오 구성 방향에 대한 답변이 부족하다.
- • 다만 엄격한 데이터셋 기준에서는 투자기간·현금흐름·손실 감내수준에 따른 구체적 구성 방향도 문서 근거가 약하므로, 권장 목표 답변은 보수안으로 반영한다.
- • E-NO-GUARANTEE-R2B 인용문에는 과거 실적이 미래 성과를 보장하지 않는다는 내용이 없으므로 해당 문구를 삭제하고 C1을 근거 범위에 맞게 축소한다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-011 · 부분 지원

**질문**

> 여유자금이 있는데 몇 년간 안정적으로 운용할 수 있는 상품을 추천해주세요. 절세 상품도 활용하고 싶습니다

**목표 답변**

> 현재 정보만으로 특정 상품을 추천하기는 어렵습니다. 안정적인 운용을 원한다면 자금의 사용 시점과 중간 인출 필요성, 감당 가능한 손실 수준을 먼저 확인해야 합니다. 연금계좌 활용을 고려하는 경우 제공 자료에서 퇴직연금에 100% 투자할 수 있는 운용방법의 예시로 제시된 상품들을 검토할 수 있으며, 연금계좌 납입에는 세액공제 혜택이 설명되어 있습니다. 다만 IRP는 법정 사유에 해당하지 않으면 부분 인출이 제한될 수 있으므로, 목돈을 쓸 계획이 있는 여유자금이라면 유동성 필요를 함께 고려해야 합니다.

**필수 주장**

- *C1** 제공 문서에서 퇴직연금에 100% 투자할 수 있는 운용방법의 예시가 제시되어 있다.
- 근거: E-IRP-SAFE-D58
- *C2** 연금계좌 납입에는 세액공제 혜택이 있다.
- 근거: E-PENSION-CREDIT-D41
- *C3** IRP 부분 인출은 법정 사유에 의해 제한된다.
- 근거: E-IRP-LIQUIDITY-D41

**문서 근거 요약**

- *E-IRP-SAFE-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view)
- `#/tables/0` · label `table`
- page/slide `1`; charspan `0:0`; bbox `{"b":179.88836669921875,"coord_origin":"BOTTOMLEFT","l":35.43013381958008,"r":557.422119140625,"t":775.9032516479492}`
- table cells `r1c1, r2c1, r3c1, r4c1, r10c1, r12c1, r13c1`
- 인용: “은행 및 우체국 예금 / 적금”
- *E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/3` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.”
- *E-IRP-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0001`
- 인용: “반면 IRP는 무주택자의 주택 구입 등 법정 사유를 충족해야 부분 인출이 가능해 까다롭다. IRP로만 운용하다 일부 금액이 필요한데 법정사유에 해당되지 않으면 전체를 해지해야 되서 불이익이 크다.”
- *E-SUITABILITY-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/32` · label `list_item`
- page/slide `2`; charspan `0:95`; bbox `{"b":631.9090909090909,"coord_origin":"BOTTOMLEFT","l":62.0,"r":525.676,"t":654.0}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- 인용: “투 자경력이나 투자성향에 적합한 상품인지 신중한 투자결정을 하시기 바랍니다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 고객의 투자기간, 거주·소득·세액공제 가능성, 위험성향과 유동성 필요가 없다.
- • 질문의 일반 여유자금이 IRP에 납입될 자금인지 확인되지 않는다.
- • E-IRP-SAFE-D58의 표에서 각 상품명과 100% 투자 가능 분류를 확인해야 하며, 확인되지 않은 상품은 목표 답변과 필수 주장에 포함하지 않는다.
- *금지 주장**
- • 특정 종목을 단정 추천하지 않는다.
- • 세액공제가 모두에게 동일하게 적용된다고 말하지 않는다.
- • 100% 투자 가능을 원금보장과 같은 의미로 말하지 않는다.
- • 퇴직연금 운용방법을 일반 여유자금 추천처럼 제시하지 않는다.
- *검토 메모**
- • 일반 여유자금 질문을 IRP 투자로 좁히지 않도록 답변을 조건부로 수정했다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-012 · 부분 지원

**질문**

> IRP 계좌에서 중도인출 등으로 안전자산 비중이 30% 미만으로 떨어지면 어떻게 처리되나요?

**목표 답변**

> 중도인출 후 비위험자산 비중이 30% 미만이 되었다면, 위험자산과 비위험자산이 전체 적립금을 구성한다는 전제에서 위험자산 비중이 70%를 초과한 상태로 볼 수 있습니다. 제공 문서에서는 IRP의 위험자산 투자 비중이 전체 적립금의 70% 이내로 제한된다는 원칙까지만 확인됩니다. 다만 이 경우 기존 위험자산의 강제매도 여부, 신규매수 제한, 유예기간 또는 비중 복원 절차는 확인되지 않으므로 단정할 수 없습니다.

**필수 주장**

- *PROD-012-C1** IRP의 위험자산 투자 비중은 전체 적립금의 70% 이내로 제한된다.
- 근거: E-IRP-70-D14, E-IRP-70-D58

**문서 근거 요약**

- *E-IRP-70-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/texts/20` · label `list_item`
- page/slide `2`; charspan `0:113`; bbox `{"b":662.1403117757872,"coord_origin":"BOTTOMLEFT","l":58.079999999999984,"r":551.2800000000003,"t":694.3199780273438}`
- retrieval `knowledge-2fa11c7e5d5c-0006`
- 인용: “위험자산(ETF, 주식형 펀드 등) 투자 비중은 전체 적립금의 70% 이내로 제한이 됩니다.”
- *E-IRP-70-D58** — [doc58.pdf](https://drive.google.com/file/d/170qgR-m-0tiUgNICe09Yr23A-1vh0dkS/view)
- `#/texts/1` · label `section_header`
- page/slide `2`; charspan `0:28`; bbox `{"b":788.6752770278034,"coord_origin":"BOTTOMLEFT","l":36.0,"r":324.53,"t":800.0399829101564}`
- 인용: “퇴직연금 적립금의 70% 까지만 투자가능한 운용방법”

**부족 근거·금지 주장**

- *부족 근거**
- • 안전자산 하한 미달 시 강제매도·매수제한·유예·복원 절차를 정한 항목이 없다.
- *금지 주장**
- • 70% 매수 한도에서 30% 하한 복원 메커니즘을 역추론하지 않는다.
- • 안전자산 30%를 항상 의무적으로 유지해야 한다고 직접 표현하지 않는다.
- *검토 메모**
- • 위험자산 70% 한도는 근거가 있으므로 `미지원`보다 `부분 지원`이 적절하다. 다만 초과 후 처리 방법은 근거가 없다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-013 · 부분 지원

**질문**

> 연금계좌에서 기타 ETF(채권형 등)의 분배금을 받았는데, 이미 한 번 과세된 뒤 나중에 연금소득세를 또 내는 이중과세 문제가 있다고 들었습니다. 지금은 어떻게 처리되나요?

**목표 답변**

> 제공 자료에서는 해당 ETF 유형의 매매차익과 분배금에 대해 인출 전까지 과세가 이연된다고 설명합니다. 또한 문서에는 2025년 1월 1일부터 국세청이 외국납부세액을 먼저 환급해 주는 단계가 사라져, 외국납부세액이 발생하는 펀드·ETF의 과세이연 효과가 낮아질 수 있다고 되어 있습니다. 다만 이 내용은 외국 배당·이자에 대한 외국납부세액이 발생하는 해외 투자분에 관한 것이므로 모든 채권형·기타 ETF에 동일하게 적용된다고 볼 수 없습니다. 질문한 ETF의 투자대상과 실제 외국 원천징수 여부 및 이후 규정 변경 여부를 확인해야 합니다.

**필수 주장**

- *C1** 제공 자료에서 설명하는 해당 ETF 유형의 매매차익과 분배금은 과세이연된다.
- 근거: E-ETF-PENSION-TAX-D43
- *C2** 문서에는 2025년 1월 1일부터 외국납부세액 선환급 단계가 사라져 외국납부세액이 발생하는 펀드·ETF의 과세이연 효과가 낮아질 수 있다고 설명되어 있다.
- 근거: E-FOREIGN-TAX-2025-D42, E-FOREIGN-DEFERRAL-D36

**문서 근거 요약**

- *E-ETF-PENSION-TAX-D43** — [doc43.docx](https://drive.google.com/file/d/1y-CkeFaTrQTYxQt2tzuXy6tn9bGXRN3n/view)
- `#/texts/20` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `f146981691bb885781b6db79ba0c93d1aa0ce3c4b04719234e31a919ccb48ceb` · Docling JSON SHA-256 `9f56706c93a4e0401eabc92ee00a4e88e32d15a2ea660447acd1a8fa0c716112`
- retrieval `knowledge-f146981691bb-0002`
- 인용: “해외주식형 월배당 ETF와 그 밖의 ETF의 경우 매매차익과 분배금 모두 과세가 이연된다.”
- *E-FOREIGN-TAX-2025-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view)
- `#/texts/19` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185`
- retrieval `knowledge-40ff19a261a2-0004`
- 인용: “2025년 이후(2025.1.1~)부터는 개정세법이 적용되어 국세청이 세액을 먼저 환급해주는 단계가 사라졌다.”
- *E-FOREIGN-DEFERRAL-D36** — [doc36.docx](https://drive.google.com/file/d/1FwipZvxX_ogEbmySP03Tgz7Q7DIBsLfF/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `9647f457ae3130d224642ee23d2284094b33568f2c3bb49542384039b49b6fe1` · Docling JSON SHA-256 `36b46f60be09cb40936a5b90df123ba668356645984b21beb735f737d8d979b0`
- 인용: “외국납부세액이 발생하는 펀드/ETF 등에 투자한다면 과세이연 효과가 낮아질 수 있다”

**부족 근거·금지 주장**

- *부족 근거**
- • 질문 속 ETF의 투자대상과 실제 원천징수 내역, 2025년 이후 추가 개정 여부가 없다.
- • 연금계좌 운용수익 전체가 기본적으로 과세이연된다는 별도 일반 근거가 연결되어 있지 않다.
- *금지 주장**
- • 모든 기타 ETF에 동일한 이중과세가 발생한다고 일반화하지 않는다.
- • 최종 세액을 상품정보 없이 계산하지 않는다.
- • 최신 규정 변경 여부를 확인하지 않고 현재 처리 방식으로 단정하지 않는다.
- *검토 메모**
- • 2025년 자료와 현재 규정의 최신성 문제가 있으므로 제공 자료의 기준 시점을 드러내고 상품별 확인이 필요하다고 제한했다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-014 · 부분 지원

**질문**

> 달러로 투자하는 채권 상품에 투자했는데, 원화 평가금액이 마이너스로 보입니다. 실제로 손해를 본 건가요?

**목표 답변**

> 원화 평가금액이 마이너스라는 표시만으로 손실 원인을 하나로 단정할 수 없습니다. 환헤지하지 않은 외화자산은 자산 자체가 올라도 원화가 외국통화보다 강해지면 원화 환산가치가 낮아질 수 있고, 채권 자체도 시장금리가 오르면 가격이 내려갈 수 있습니다. 따라서 환율과 채권가격 요인이 함께 작용할 수 있으며, 실제 확정손익 판단에는 매입가격·현재 채권가격·적용환율·매도나 환전 여부가 필요합니다.

**필수 주장**

- *C1** 환헤지하지 않은 외화자산은 원화 강세 때 원화 환산가치가 낮아질 수 있다.
- 근거: E-FX-RISK-R2B
- *C2** 시장금리 상승은 채권가치 하락을 만들 수 있다.
- 근거: E-BOND-RATE-R2B

**문서 근거 요약**

- *E-FX-RISK-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/43` · label `table`
- page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- table cells `r6c1`
- 인용: “원화의 가치가 외국통화에 비하여 상대적으로 더 높아지면, 외화자산인 투자자산의 가치는 원화가치로 환산했을 때 낮아집니다.”
- *E-BOND-RATE-R2B** — [R2_KR5153450112.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/43` · label `table`
- page/slide `23`; charspan `0:0`; bbox `{"b":178.79119873046875,"coord_origin":"BOTTOMLEFT","l":44.034080505371094,"r":556.08740234375,"t":586.7637939453125}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5153450112--3644772b6ffd--docling-no-ocr-native-v1`
- table cells `r3c1`
- 인용: “시장이자율이 상승하는 경우 채권가격을 결정하는 할인율이 함께 상승함에 따라 그 가치가 하락”

**부족 근거·금지 주장**

- *부족 근거**
- • 계좌 화면의 평가손익 정의, 매입가격·환율·현재가와 실현 거래가 없다.
- *금지 주장**
- • 환전 전에는 손해가 아니라고 절대화하지 않는다.
- • 환율만을 유일한 원인으로 확정하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### PROD-015 · 부분 지원

**질문**

> 배당이 나오는 해외 ETF에 투자하려고 합니다. 배당금이 나오면 자동으로 재투자되는 기능이 있나요? 그리고 이런 상품은 연금계좌 등 어떤 계좌에서 투자할 수 있나요?

**목표 답변**

> 문서는 연금저축·IRP에서 국내에 상장된 해외 ETF에 투자하는 경우를 확인해 줍니다. 반면 해외 거래소 상장 ETF를 직접 거래할 수 있는 연금계좌가 무엇인지, 배당금을 자동으로 같은 ETF에 재투자하는 회사 서비스가 있는지는 확인해 주지 않습니다. 국내상장 상품인지 해외상장 직접투자 상품인지 먼저 구분하고, 자동재투자 기능과 현재 거래가능 계좌는 회사의 최신 서비스·상품 목록에서 확인해야 합니다.

**필수 주장**

- *C1** 연금저축·IRP에서 국내상장 해외 ETF 투자와 과세이연이 문서화되어 있다.
- 근거: E-OVERSEAS-ETF-D42
- *C2** 퇴직연금 거래가능 ETF는 최신 목록에서 확인해야 한다.
- 근거: E-ETF-LIVE-LIST-D53

**문서 근거 요약**

- *E-OVERSEAS-ETF-D42** — [doc42.docx](https://drive.google.com/file/d/18ZzU0lDyjVt5irbfVj4hOM2k9OylFRow/view)
- `#/texts/15` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40ff19a261a2c4bb46ebe3b4c88754dcf38ee23a0d38c6901fbe28c8add8fe18` · Docling JSON SHA-256 `f20a4ff800217c83d13ffae9ab160eb2927ece28368361e46aa7ef08b9e9e185`
- 인용: “국내 상장 해외 ETF에 투자 시 과세이연효과가 있다.”
- *E-ETF-LIVE-LIST-D53** — [doc53.pdf](https://drive.google.com/file/d/1SWG73gR8eYUtuUEHR_XMGZW6uuVLFUlJ/view)
- `#/texts/11` · label `list_item`
- page/slide `1`; charspan `0:194`; bbox `{"b":293.26645349839157,"coord_origin":"BOTTOMLEFT","l":56.04,"r":559.54,"t":365.4019829101563}`
- 인용: “퇴직연금에서 거래가능한 ETF 는 홈페지지 , MTS(M STOCK) 에서 확인 가능”

**부족 근거·금지 주장**

- *부족 근거**
- • 해외상장 ETF 직접거래 가능 계좌와 회사의 배당 자동재투자 서비스 규칙이 없다.
- *금지 주장**
- • 펀드 내부 분배금 재투자 조항을 증권계좌 DRIP 서비스로 오인하지 않는다.
- • 국내상장 해외 ETF와 해외상장 ETF를 혼동하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

## 업무·제도 (15개)

### POLICY-001 · 부분 지원

**질문**

> 연금저축계좌에 올해 한도보다 많은 금액을 실수로 입금했습니다. 페널티 없이 뺄 방법이 있을까요?

**목표 답변**

> 먼저 초과분이 세액공제를 받지 않은 납입원금인지 확인해야 합니다. 문서상 세액공제를 받지 않은 납입금은 인출순서상 먼저 빠지고 비과세이며, 연금저축펀드는 필요한 금액을 부분 인출할 수 있습니다. 다만 ‘올해 넣은 초과분이면 모두 페널티 없음’이라는 별도 규정과 상품별 수수료는 문서에서 확인되지 않으므로, 해당 금액의 세액공제 반영 여부와 과세재원 구분을 확인한 뒤 인출해야 합니다.

**필수 주장**

- *C1** 세액공제를 받지 않은 납입금은 먼저 인출되고 비과세다.
- 근거: E-NONDEDUCTED-WITHDRAW-D44, E-NONDEDUCTED-TAXFREE-D39
- *C2** 연금저축펀드는 부분 인출이 가능하나 과세재원에는 세금이 적용될 수 있다.
- 근거: E-LIQUIDITY-D41

**문서 근거 요약**

- *E-NONDEDUCTED-WITHDRAW-D44** — [doc44.docx](https://drive.google.com/file/d/1fzuDWMXAYHGdgeClu3l0gUhZkr9KGiKY/view)
- `#/texts/8` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `09fa92de548b4cf1fb2ba1bfa0115bdbccf33c237626ed668bf58c758a249ed0` · Docling JSON SHA-256 `f7bbf4b8ae33cb1afd5def53d444c208b8723be428b188d774501c479c6f3719`
- retrieval `knowledge-09fa92de548b-0001`
- 인용: “세액공제받지 않은 납입금은 비과세되는데 제일 먼저 인출된다.”
- *E-NONDEDUCTED-TAXFREE-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view)
- `#/texts/16` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27`
- 인용: “세액공제를 받지 않은 납입금(ISA전환금 포함)이 있을 경우 인출할 때에도 전액 비과세”
- *E-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0001`
- 인용: “연금저축펀드는 부분 인출이 자유롭다. 원할 때 필요한 금액을 인출할 수 있다. 물론 인출금액이 과세재원이면 16.5% 기타소득세가 적용된다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 당해연도 초과입금 자체를 별도 면책하는 규정과 상품별 수수료가 없다.
- • 질문의 ‘한도’가 연간 납입한도인지 세액공제 대상 한도인지 명확하지 않다.
- *금지 주장**
- • 당해연도 납입금 전부를 무조건 무세금 인출 가능하다고 말하지 않는다.
- • 초과입금이라는 이유만으로 무조건 비과세라고 단정하지 않는다.
- *검토 메모**
- • OK. 초과분의 세액공제 반영 여부와 과세재원 구분을 먼저 확인하도록 안내하고 있어 위험한 단정을 피한다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-002 · 직접 지원

**질문**

> 개인연금 수령 개시 시기를 늦추고 싶습니다. 연금 개시는 조건이 되면 자동으로 시작되나요?

**목표 답변**

> 자동으로 지급이 시작되는 것은 아닙니다. 문서상 연금저축의 일반 납입요건은 가입기간 5년 이상이고, 수령은 55세 이후 연간 연금수령한도 안에서 가입자가 수령개시를 신청한 뒤 인출하는 구조입니다. 따라서 조건을 충족해도 신청하지 않으면 개시를 늦출 수 있습니다. 다만 퇴직금 재원 등에는 가입기간 예외가 있을 수 있으므로 계좌 재원을 함께 확인해야 합니다.

**필수 주장**

- *C1** 연금 인출은 55세 이후 가입자의 수령개시 신청 후 이루어진다.
- 근거: E-PENSION-START-R2

**문서 근거 요약**

- *E-PENSION-START-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/42` · label `table`
- page/slide `43`; charspan `0:0`; bbox `{"b":108.07574462890625,"coord_origin":"BOTTOMLEFT","l":55.51258850097656,"r":541.406982421875,"t":636.6895446777344}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1`
- table cells `r1c1, r2c1`
- retrieval `prospectus-e66c18ed3f86-0120`
- 인용: “가입자의 수령개시 신청 후 인출”

**부족 근거·금지 주장**

- *금지 주장**
- • 나이 도달만으로 자동 지급된다고 말하지 않는다.
- • 모든 재원에 가입기간 5년을 예외 없이 적용하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-003 · 직접 지원

**질문**

> IRP 계좌에 있는 돈을 출금하고 싶습니다. 어떻게 해야 하나요?

**목표 답변**

> 만 55세 전 IRP 부분 인출은 법에 열거된 사유에 해당할 때만 가능합니다. 문서에 든 사유는 무주택자의 본인 명의 주택 구입, 주거 목적 전세보증금, 가입자나 부양가족의 6개월 이상 요양, 파산·개인회생, 정해진 천재지변 사유 등입니다. 사유에 해당하지 않으면 일반적인 부분 인출은 불가능하고 전체 해지가 필요할 수 있으며, 세금은 계좌 재원과 인출 사유에 따라 달라집니다. 연금 수령 요건을 충족했다면 연금개시 신청 경로도 함께 검토해야 합니다.

**필수 주장**

- *C1** IRP는 법정 사유가 아니면 만 55세 전 중도인출이 불가능하다.
- 근거: E-IRP-WITHDRAW-D20
- *C2** 주택구입·전세보증금·요양·파산·회생·천재지변 등이 법정 사유로 열거된다.
- 근거: E-IRP-REASONS-D20
- *C3** 법정 사유가 아닌 부분 인출은 전체 해지가 필요할 수 있다.
- 근거: E-IRP-LIQUIDITY-D41

**문서 근거 요약**

- *E-IRP-WITHDRAW-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847`
- retrieval `knowledge-977c9fc53894-0000`
- 인용: “중도인출 사유를 법으로 열거하고 있어서, 사유에 해당하지 않으면 만 55세 이전에는 중도인출 자체가 불가능하다.”
- *E-IRP-REASONS-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view)
- `#/tables/0` · label `table`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847`
- table cells `r1c0, r2c0, r3c0, r4c0, r5c0`
- 인용: “무주택자인 가입자가 본인 명의로 주택 구입”
- *E-IRP-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0001`
- 인용: “반면 IRP는 무주택자의 주택 구입 등 법정 사유를 충족해야 부분 인출이 가능해 까다롭다. IRP로만 운용하다 일부 금액이 필요한데 법정사유에 해당되지 않으면 전체를 해지해야 되서 불이익이 크다.”
- *E-PENSION-START-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/tables/42` · label `table`
- page/slide `43`; charspan `0:0`; bbox `{"b":108.07574462890625,"coord_origin":"BOTTOMLEFT","l":55.51258850097656,"r":541.406982421875,"t":636.6895446777344}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1`
- table cells `r1c1, r2c1`
- retrieval `prospectus-e66c18ed3f86-0120`
- 인용: “가입자의 수령개시 신청 후 인출”

**부족 근거·금지 주장**

- *금지 주장**
- • 모든 출금을 같은 세율로 설명하지 않는다.
- • 법정 사유 확인 없이 부분 인출 가능하다고 답하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-004 · 부분 지원

**질문**

> 사업자등록번호가 없는 프리랜서인데 IRP 계좌를 개설할 수 있나요? 가능하다면 어떤 서류가 필요한가요?

**목표 답변**

> 문서상 IRP 가입대상에는 자영업자가 포함됩니다. 그러나 사업자등록번호가 없는 프리랜서를 어떤 자격으로 판단하는지와 건강보험자격득실확인서·소득금액증명원 같은 대체서류 목록은 제공 문서에서 확인되지 않습니다. 따라서 소득·근로 형태를 확인한 뒤 현재 회사의 계좌개설 자격 및 대체 증빙서류 안내를 별도로 확인해야 합니다.

**필수 주장**

- *C1** IRP 가입대상에 자영업자가 포함된다.
- 근거: E-SELF-EMPLOYED-D14, E-PENSION-ELIGIBILITY-D41

**문서 근거 요약**

- *E-SELF-EMPLOYED-D14** — [doc14.pdf](https://drive.google.com/file/d/1IWjPbxaUImnycVgXbAe3wMtZGNr5nafa/view)
- `#/tables/0` · label `table`
- page/slide `1`; charspan `0:0`; bbox `{"b":126.7911376953125,"coord_origin":"BOTTOMLEFT","l":62.790504455566406,"r":547.125,"t":355.3334045410156}`
- table cells `r2c0`
- 인용: “①자영업자”
- *E-PENSION-ELIGIBILITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/5` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- 인용: “IRP는 직장인, 자영업자, 직역연금가입자 등 가입대상이 정해져 있다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 무등록 프리랜서의 자격판정과 대체 증빙서류 목록이 없다.
- *금지 주장**
- • 문서에 없는 대체서류 목록을 생성하지 않는다.
- • 자영업자라는 표현만으로 모든 프리랜서 가입을 확정하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-005 · 미지원

**질문**

> 연금계좌 연간 납입한도를 다 채우지 못했는데, 남은 한도를 다음 해로 이월해서 쓸 수 있나요?

**목표 답변**

> 제공 문서에는 연금저축·IRP 합산 연간 납입한도가 적혀 있지만, 연금계좌의 미사용 한도를 다음 해로 이월할 수 있는지 여부를 직접 정한 항목은 없습니다. ISA 한도가 이월된다는 문구는 확인되지만 이를 연금계좌에 반대로 적용할 수는 없으므로, 이 문서 집합만으로 ‘이월 불가’를 정답으로 확정할 수 없습니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거 요약**

- *E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.”
- *E-ISA-CARRY-CONTEXT-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view)
- `#/texts/15` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235`
- 인용: “ISA는 매년 2천만원까지 입금이 가능한데 한도는 이월되서 누적”

**부족 근거·금지 주장**

- *부족 근거**
- • 연금계좌 미사용 납입한도의 이월 가능 또는 불가를 직접 명시한 항목이 없다.
- *금지 주장**
- • ISA의 이월 규정을 연금계좌 규정으로 전용하지 않는다.
- • 연간 한도라는 표현만으로 비이월을 추론하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-006 · 직접 지원

**질문**

> 연금저축계좌에서 보유 중인 펀드를 매도하고 다른 펀드로 교체하려고 합니다. 이렇게 계좌 내에서 상품을 바꾸면 이미 받은 세액공제가 추징되나요?

**목표 답변**

> 계좌를 유지한 채 연금저축계좌 안에서 펀드 수익증권을 환매하는 시점에는 별도로 과세하지 않습니다. 과세는 연금저축계좌에서 자금을 인출할 때 재원과 수령 방식에 따라 판단됩니다. 따라서 단순한 계좌 내 펀드 매도·교체만으로 이미 받은 세액공제가 곧바로 추징되는 것은 아닙니다. 다만 매도대금을 계좌 밖으로 인출하면 별도의 과세 판단이 필요합니다.

**필수 주장**

- *C1** 연금저축계좌 내 수익증권 환매 시 별도 과세하지 않고 자금 인출 시 과세한다.
- 근거: E-FUND-SWITCH-TAX-R2

**문서 근거 요약**

- *E-FUND-SWITCH-TAX-R2** — [R2_KR5113420012.pdf](https://drive.google.com/drive/folders/1Iq0lv7hRZ2M-95I1FV-pGky0rQxBrtxV)
- `#/texts/559` · label `list_item`
- page/slide `43`; charspan `0:154`; bbox `{"b":658.4216083916084,"coord_origin":"BOTTOMLEFT","l":79.56,"r":533.2800000000001,"t":700.22}`
- Drive archive `docling_bundles_20260826.tar.gz` · member `R2_KR5113420012--e66c18ed3f86--docling-no-ocr-native-v1`
- retrieval `prospectus-e66c18ed3f86-0119`
- 인용: “수익증권을 환매하는 시점에 별도의 과세를 하지 않으며, 연금저축계좌에서 자 금 인출시 다음과 같이 과세”

**부족 근거·금지 주장**

- *금지 주장**
- • 계좌 내 매도와 계좌 밖 인출을 같은 행위로 취급하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-007 · 직접 지원

**질문**

> ISA가 만기되면 연금계좌로 전환할 수 있다고 알고 있습니다. 이때 비과세 한도를 초과한 수익 부분은 세금을 내고 나서 이전되나요, 아니면 세금 없이 그대로 이전되나요?

**목표 답변**

> ISA 자산이 세금 없이 그대로 현물 이전되는 구조가 아닙니다. 문서상 ISA를 만기해지할 때 순손익 중 일반형 200만원·서민형 400만원까지 비과세하고 초과 수익은 9.9%로 저율과세한 뒤, 그렇게 세제처리된 만기자금을 60일 안에 연금저축이나 IRP로 옮길 수 있습니다. 즉 ISA의 만기 정산·해지가 먼저이고 연금계좌 전환입금은 그 다음 별도 절차입니다.

**필수 주장**

- *C1** ISA 만기 순손익은 비과세 한도와 초과분 9.9% 저율과세로 정산된다.
- 근거: E-ISA-SETTLE-D23
- *C2** 세제처리된 만기자금은 60일 안에 연금계좌로 옮길 수 있다.
- 근거: E-ISA-SETTLE-D23, E-ISA-60-CALENDAR-D6

**문서 근거 요약**

- *E-ISA-SETTLE-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view)
- `#/texts/3` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235`
- retrieval `knowledge-ba39df5f7ed5-0000`
- 인용: “순손익에 대해 200만원(서민형은 400만원)까지 비과세하고 초과된 수익은 9.9%로 저율과세된다.”
- *E-ISA-60-CALENDAR-D6** — [doc6.docx](https://drive.google.com/file/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/view)
- `#/texts/57` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9`
- 인용: “60일은 캘린더 기준, 만기일자 불산입”

**부족 근거·금지 주장**

- *금지 주장**
- • ISA 보유자산이 세금 없이 자동 현물 이전된다고 말하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-008 · 부분 지원

**질문**

> 다른 증권사 CMA 계좌에 있는 자금을 우리 회사 CMA 계좌로 이체하면 연말정산 세액공제 대상 금액에 영향이 있나요?

**목표 답변**

> 제공 문서가 세액공제 대상으로 설명하는 것은 연금저축·IRP 같은 연금계좌의 납입액입니다. 따라서 일반 CMA끼리의 자금 이동을 연금계좌 납입 세액공제액으로 잡을 근거는 없습니다. 다만 CMA 이체와 세액공제의 무관성을 직접 명시한 문서는 없으므로, 실제 세액공제 대상액은 해당 과세기간의 연금저축·IRP 납입 내역으로 확인해야 합니다.

**필수 주장**

- *C1** 문서상 세액공제는 연금계좌 납입액을 기준으로 설명된다.
- 근거: E-PENSION-CREDIT-D41, E-PENSION-LIMITS-D41

**문서 근거 요약**

- *E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/3` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.”
- *E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.”

**부족 근거·금지 주장**

- *부족 근거**
- • CMA 간 이체가 세액공제에 미치는 영향을 직접 명시한 항목은 없다.
- *금지 주장**
- • CMA를 연금계좌로 취급하지 않는다.
- • 개인별 공제액을 납입 내역 없이 계산하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-009 · 부분 지원

**질문**

> 연금계좌에 넣은 돈에 대해 세액공제를 아예 신청하지 않으면, 나중에 연금으로 받을 때 연금소득세도 안 내도 된다고 들었습니다. 맞나요?

**목표 답변**

> 제공 자료에서는 세액공제를 받지 않은 납입원금이 인출 시 비과세된다고 설명합니다. 다만 이 내용만으로 세액공제를 신청하지 않은 경우 계좌의 운용수익을 포함한 모든 재원이 비과세된다고 판단할 수는 없습니다. 또한 DC·IRP 과세재원확정 업무에서는 국세청의 연금보험료등 소득·세액공제확인서를 통한 내점 처리가 안내되어 있지만, 이를 모든 연금저축계좌에 동일하게 적용할 근거는 부족합니다. 따라서 계좌 유형과 미공제 납입금의 과세제외 반영 절차를 확인해야 합니다.

**필수 주장**

- *C1** 세액공제를 받지 않은 납입원금은 인출 시 비과세다.
- 근거: E-NONDEDUCTED-TAXFREE-D39
- *C2** DC·IRP 과세재원확정에는 국세청 확인서와 내점 절차가 문서화되어 있다.
- 근거: E-NONTAX-PROCESS-D19, E-NONTAX-DOCUMENT-D19, E-NONTAX-INPERSON-D19

**문서 근거 요약**

- *E-NONDEDUCTED-TAXFREE-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view)
- `#/texts/16` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27`
- 인용: “세액공제를 받지 않은 납입금(ISA전환금 포함)이 있을 경우 인출할 때에도 전액 비과세”
- *E-NONTAX-PROCESS-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view)
- `#/texts/3` · label `text`
- page/slide `1`; charspan `0:44`; bbox `{"b":670.5152770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":477.72592000000003,"t":679.9479829101563}`
- 인용: “초과하는 과세대상금액을 과세제외함으로써 과세대상금액을 일치시켜주는 업무입니다 .”
- *E-NONTAX-DOCUMENT-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view)
- `#/texts/6` · label `text`
- page/slide `1`; charspan `0:28`; bbox `{"b":545.2052770278033,"coord_origin":"BOTTOMLEFT","l":72.024,"r":292.99592,"t":554.6379829101562}`
- 인용: “연금보험료등 소득·세액공제확인서 ( 국세청자료 )”
- *E-NONTAX-INPERSON-D19** — [doc19.pdf](https://drive.google.com/file/d/1Pldykf0Dt_E10_oVbZjM1VPN3ivrEajg/view)
- `#/texts/8` · label `text`
- page/slide `1`; charspan `0:6`; bbox `{"b":491.92527702780336,"coord_origin":"BOTTOMLEFT","l":131.78,"r":186.74,"t":501.3579829101563}`
- 인용: “내점만 가능”

**부족 근거·금지 주장**

- *부족 근거**
- • doc19의 DC·IRP 절차를 일반 연금저축까지 동일 적용한다는 근거가 없다.
- • 운용수익과 세액공제를 받은 재원의 과세 여부까지 직접 확정하는 별도 근거가 없다.
- *금지 주장**
- • 세액공제 미신청만으로 계좌의 모든 재원이 비과세라고 말하지 않는다.
- • 모든 계좌에 자동 과세제외가 된다고 말하지 않는다.
- • DC·IRP 절차를 모든 연금저축계좌에 그대로 적용하지 않는다.
- *검토 메모**
- • 비과세로 확정하는 범위는 미공제 납입원금으로 제한했다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-010 · 미지원

**질문**

> ISA 계좌 만기 연장 신청 시점을 놓쳤습니다. 만기가 지난 계좌를 다시 연장할 수 있나요?

**목표 답변**

> 제공 문서에서는 ISA의 만기연장과 재가입이 가능하다는 일반적인 내용은 확인됩니다. 다만 만기연장 신청 시점을 놓쳐 이미 만기가 지난 동일 계좌를 다시 연장할 수 있는지, 별도의 유예기간이나 처리 절차가 있는지는 확인되지 않습니다. 따라서 연장 가능 여부를 단정할 수 없으며, 해당 계좌의 약관과 현재 업무규정을 추가로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거 요약**

- *E-ISA-EXTEND-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view)
- `#/tables/2` · label `table`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235`
- table cells `r1c2`
- 인용: “1인 1개 보유 (만기연장/재가입 가능)”
- *E-ISA-60-CALENDAR-D6** — [doc6.docx](https://drive.google.com/file/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/view)
- `#/texts/57` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9`
- 인용: “60일은 캘린더 기준, 만기일자 불산입”

**부족 근거·금지 주장**

- *부족 근거**
- • 만기 경과 후 연장 가능 여부와 30일 세제혜택 소멸 규정이 없다.
- *금지 주장**
- • 연금전환 60일 기한을 만기연장 기한으로 바꾸지 않는다.
- • 근거 없는 30일 규칙을 생성하지 않는다.
- *검토 메모**
- • 미지원 판정은 적절하나, 목표 답변은 만기 경과 후 연장 가능 여부를 확인할 수 없다는 결론에 집중하도록 수정했다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-011 · 부분 지원

**질문**

> 오래전(2013년 이전)에 가입한 연금계좌를 다른 금융회사로 이전하려고 합니다. 가입일을 그대로 승계받으면 연금수령연차 계산에서 유리하다고 들었는데, 어떤 조건에서 그렇게 되나요?

**목표 답변**

> 문서상 정확한 기준일은 2013년 3월 1일입니다. 그 이전 가입 연금계좌는 연금수령연차를 6년차부터 기산합니다. 또 2013년 3월 1일 이전 DC·DB 가입자는 퇴직금 전액을 신규 연금계좌로 이체하는 경우에 한해 6년차 특례를 적용받을 수 있다고 설명합니다. 그러나 일반적인 금융회사 간 연금계좌 이전 때 원래 가입일이 어떤 조건으로 승계되는지는 제공 문서에 없어, 해당 이전계약의 가입일 승계 여부를 별도로 확인해야 합니다.

**필수 주장**

- *C1** 2013년 3월 1일 이전 가입 연금계좌는 연금수령연차를 6년차부터 기산한다.
- 근거: E-OLD-PENSION-YEAR-D39
- *C2** 2013년 3월 1일 이전 DC·DB는 퇴직금 전액을 신규 연금계좌로 이체할 때 특례가 적용된다.
- 근거: E-OLD-DC-TRANSFER-D39

**문서 근거 요약**

- *E-OLD-PENSION-YEAR-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view)
- `#/texts/11` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27`
- 인용: “2013년 3월 1일 이전 가입한 연금계좌는 6년차로 기산한다.”
- *E-OLD-DC-TRANSFER-D39** — [doc39.docx](https://drive.google.com/file/d/15H0iol0uk2Q5plNdOUM75c4bPCrafwqh/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `fcf61c7874abaa74fcd79cceda567ea2f5ade6044d34d975cd102c343f9c5017` · Docling JSON SHA-256 `5e255b8f816e443729103bf2b8db5a689cf2a3df8619eb771aedec59fd1bcb27`
- 인용: “DC/DB 퇴직금 전액을 신규 연금계좌로 이체하는 경우에 한하여 6년차 특례”

**부족 근거·금지 주장**

- *부족 근거**
- • 일반 금융회사 간 연금계좌 이전 시 가입일 승계 조건이 없다.
- • 2013년 3월 1일 이전 가입 연금계좌 특례와 DC·DB 퇴직금 전액 이체 특례의 적용 관계를 문맥상 추가 확인해야 한다.
- *금지 주장**
- • 일반적인 연금계좌 이전에서 기존 가입일이 자동 승계된다고 단정하지 않는다.
- • DC·DB 전액 이체 특례의 날짜 조건을 문서 문맥 확인 없이 확정하지 않는다.
- *검토 메모**
- • 보류. doc39.docx의 앞뒤 문맥을 확인해 DC·DB 전액이체 특례에도 2013년 3월 1일 이전 조건이 적용되는지 검증해야 한다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [ ] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다 (원문 확인 전 미반영 — C2의 특례 조건이 C1과 동일한 2013.3.1 기준을 공유하는지 doc39.docx 문맥 확인 필요)
- [x] 금지 주장을 답변하지 않는다

### POLICY-012 · 미지원

**질문**

> ISA 계좌의 의무가입기간 3년이 되는 날짜가 토요일입니다. 휴일이 낀 경우 해지·재가입 처리는 어떻게 되나요?

**목표 답변**

> 제공 문서에서는 ISA의 만기연장과 재가입이 가능하다는 일반적인 내용은 확인됩니다. 다만 ISA 의무가입기간이 3년이라는 점, 의무가입기간 종료일이 토요일이나 휴일인 경우 어느 영업일에 해지·재가입 처리하는지, 별도의 유예기간이나 처리 절차가 있는지는 확인되지 않습니다. 따라서 휴일이 낀 경우의 해지·재가입 처리 방식을 단정할 수 없으며, 해당 계좌의 약관과 현재 업무규정을 추가로 확인해야 합니다.

**필수 주장**

- 직접 확정할 필수 주장 없음

**문서 근거 요약**

- *E-ISA-EXTEND-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view)
- `#/tables/2` · label `table`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235`
- table cells `r1c2`
- 인용: “1인 1개 보유 (만기연장/재가입 가능)”

**부족 근거·금지 주장**

- *부족 근거**
- • ISA 만기일이 휴일일 때 적용할 영업일 산정 규칙이 없다.
- • 현재 연결 근거만으로는 ISA 의무가입기간 3년을 직접 확인하기 어렵다.
- *금지 주장**
- • 디폴트옵션 등 다른 제도의 휴일 규칙을 ISA에 전용하지 않는다.
- • 직전 또는 다음 영업일을 근거 없이 선택하지 않는다.
- *검토 메모**
- • 미지원 판정은 유지한다. 현재 근거는 만기연장·재가입 가능성만 부분적으로 뒷받침한다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-013 · 직접 지원

**질문**

> ISA가 만기됐는데 전액이 아니라 일부 금액만 연금계좌로 이전해서 추가 세액공제를 받고, 나머지는 다른 계좌로 옮기고 싶습니다. 가능한가요? 세금 문제는 없나요?

**목표 답변**

> 가능합니다. ISA 만기해지금액의 전부 또는 일부를 만기일 다음 날부터 계산한 60일의 캘린더 기간 안에 연금계좌로 전환입금할 수 있고, 해지금액 범위에서는 여러 차례 나누어 입금할 수도 있습니다. 추가 세액공제 대상은 전환입금액의 10%이며 최대 300만원입니다. 다만 ISA 자체는 먼저 만기해지하면서 비과세 한도와 초과수익 9.9% 저율과세로 정산되고, 연금계좌로 넣지 않은 나머지 자금은 일반 자금으로 옮기는 구조입니다.

**필수 주장**

- *C1** ISA 만기해지금액의 전부 또는 일부를 60일 안에 연금계좌로 입금할 수 있다.
- 근거: E-ISA-PARTIAL-D6, E-ISA-60-CALENDAR-D6
- *C2** 해지금액 범위에서 60일 안에 횟수 제한 없이 나눠 입금할 수 있다.
- 근거: E-ISA-REPEAT-D33
- *C3** 추가 세액공제는 전환입금액의 10%, 최대 300만원이다.
- 근거: E-ISA-CREDIT-D33
- *C4** ISA는 만기해지 때 세제 정산을 먼저 한다.
- 근거: E-ISA-SETTLE-D23

**문서 근거 요약**

- *E-ISA-PARTIAL-D6** — [doc6.docx](https://drive.google.com/file/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/view)
- `#/texts/51` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9`
- retrieval `knowledge-0bc7cd31e0cb-0004`
- 인용: “ISA 만기해지금액의 전부 또는 일부를 만기일로부터 60일 이내 개인IRP로 입금가능”
- *E-ISA-60-CALENDAR-D6** — [doc6.docx](https://drive.google.com/file/d/1LScuVYuY70I1Po7jhRCE87OfRSbFyiGy/view)
- `#/texts/57` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `0bc7cd31e0cbf6ffcfd72a5e22b0b8cc10f2e65ecb996ea86f0d1419701b0fb2` · Docling JSON SHA-256 `57785a10c8e5167c0568dfbbca8e2e19a85e907375c73135de28f6e1e16143b9`
- 인용: “60일은 캘린더 기준, 만기일자 불산입”
- *E-ISA-REPEAT-D33** — [doc33.pptx](https://drive.google.com/file/d/1gF7eKVvP9VNjqDvQo4Z_n6lgmmFqCEO-/view)
- `#/texts/65` · label `list_item`
- page/slide `5`; charspan `0:43`; bbox `{"b":1643154.0,"coord_origin":"BOTTOMLEFT","l":954821.0,"r":9290760.0,"t":2104819.0}`
- 인용: “ISA 만기 해지된 금액 내에서 60일 이내 횟수 제한 없습니다.”
- *E-ISA-CREDIT-D33** — [doc33.pptx](https://drive.google.com/file/d/1gF7eKVvP9VNjqDvQo4Z_n6lgmmFqCEO-/view)
- `#/texts/82` · label `paragraph`
- page/slide `6`; charspan `0:110`; bbox `{"b":1497989.0,"coord_origin":"BOTTOMLEFT","l":1158061.0,"r":10529061.0,"t":2328986.0}`
- 인용: “ISA전환 입금 금액의 10%(최대 300만원)”
- *E-ISA-SETTLE-D23** — [doc23.docx](https://drive.google.com/file/d/1oWF-nSRlvYQtbAILsRdhhn6mSBV0CIRn/view)
- `#/texts/3` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `ba39df5f7ed5ad3fb47caa2ca31545d6a1586a40620ea934a6a5cb29eb6b9d40` · Docling JSON SHA-256 `53b268b4da37aa24b0ad9b09ada6f0c70a7b23917d7af578f30a45109f648235`
- retrieval `knowledge-ba39df5f7ed5-0000`
- 인용: “순손익에 대해 200만원(서민형은 400만원)까지 비과세하고 초과된 수익은 9.9%로 저율과세된다.”

**부족 근거·금지 주장**

- *금지 주장**
- • ISA 자산이 세금 없이 자동 이전된다고 말하지 않는다.
- • 전환금액 전부가 추가 세액공제 대상이라고 말하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-014 · 직접 지원

**질문**

> 가족의 갑작스러운 경제적 어려움으로 개인연금과 퇴직연금 자금을 최대한 인출해야 하는 상황입니다. 세금 불이익을 최소화하면서 인출할 수 있는 방법과 절차를 알고 싶습니다

**목표 답변**

> ‘가족의 경제적 어려움’만으로 IRP의 법정 중도인출 사유라고 단정할 수는 없습니다. 먼저 계좌를 구분해야 합니다. 연금저축은 사유와 무관하게 부분 인출할 수 있지만 과세재원을 인출하면 세금이 붙을 수 있습니다. IRP는 무주택자의 주택 구입·전세보증금, 가입자나 부양가족의 6개월 이상 요양, 파산·개인회생, 정해진 천재지변 등 법정 사유에 해당해야 부분 인출할 수 있고, 아니면 전체 해지가 필요할 수 있습니다. 따라서 실제 사정이 어느 법정 사유에 해당하는지와 계좌별 과세재원을 확인한 뒤 필요한 금액만 인출하는 순서로 검토해야 합니다.

**필수 주장**

- *C1** 연금저축은 부분 인출 가능하나 과세재원에는 세금이 적용될 수 있다.
- 근거: E-LIQUIDITY-D41
- *C2** IRP는 열거된 법정 사유에 해당해야 부분 인출할 수 있다.
- 근거: E-IRP-WITHDRAW-D20, E-IRP-REASONS-D20
- *C3** 법정 사유가 아니면 IRP 전체 해지가 필요할 수 있다.
- 근거: E-IRP-LIQUIDITY-D41

**문서 근거 요약**

- *E-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0001`
- 인용: “연금저축펀드는 부분 인출이 자유롭다. 원할 때 필요한 금액을 인출할 수 있다. 물론 인출금액이 과세재원이면 16.5% 기타소득세가 적용된다.”
- *E-IRP-LIQUIDITY-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/12` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0001`
- 인용: “반면 IRP는 무주택자의 주택 구입 등 법정 사유를 충족해야 부분 인출이 가능해 까다롭다. IRP로만 운용하다 일부 금액이 필요한데 법정사유에 해당되지 않으면 전체를 해지해야 되서 불이익이 크다.”
- *E-IRP-WITHDRAW-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847`
- retrieval `knowledge-977c9fc53894-0000`
- 인용: “중도인출 사유를 법으로 열거하고 있어서, 사유에 해당하지 않으면 만 55세 이전에는 중도인출 자체가 불가능하다.”
- *E-IRP-REASONS-D20** — [doc20.docx](https://drive.google.com/file/d/16Lr4-mcSSK5bjJm24tEKGoT7mrOcm4mp/view)
- `#/tables/0` · label `table`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `977c9fc5389454a85a09e6ca0fe0afbf8fd5f0da4edfae0d408ed2fe4c591f3a` · Docling JSON SHA-256 `886cb1513124c0d2618f837ef910dc7cc483c0ce82fe5791883b28fc8c227847`
- table cells `r1c0, r2c0, r3c0, r4c0, r5c0`
- 인용: “무주택자인 가입자가 본인 명의로 주택 구입”

**부족 근거·금지 주장**

- *금지 주장**
- • 일반적인 경제적 곤란을 자동 법정 사유로 인정하지 않는다.
- • 개별 사실과 과세재원 없이 최소세액을 확정하지 않는다.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

### POLICY-015 · 최신성 공백

**질문**

> 예전에 있었던 소득공제 장기펀드 같은 상품이 지금도 있나요? 지금은 어떤 상품으로 세액공제를 받을 수 있나요?

**목표 답변**

> 제공 자료만으로는 소득공제 장기펀드의 제도 종료 시점이나 2026년 현재 신규가입 가능 여부를 확인할 수 없습니다. 따라서 과거 상품명이 자료에 등장한다는 이유만으로 현재도 가입할 수 있다고 판단해서는 안 됩니다. 한편 제공 자료에서는 연금저축과 IRP 납입을 세액공제 대상으로 설명하고 있으며, 자료 작성 시점 기준으로 세액공제 대상 납입한도는 연금저축이 연 600만 원, IRP는 연금저축 납입액을 포함하여 합산 연 900만 원으로 제시됩니다. 다만 이 한도가 2026년 현재도 그대로 적용되는지는 이 자료만으로 확인할 수 없으므로, 현재 적용 가능 여부와 구체적인 기준은 해당 연도의 규정을 추가로 확인해야 합니다.

**필수 주장**

- *C1** 제공 문서에서는 연금저축과 IRP 납입을 세액공제 대상으로 설명한다.
- 근거: E-PENSION-CREDIT-D41
- *C2** 제공 문서상 세액공제 대상 납입한도는 연금저축 연 600만 원, IRP는 연금저축 납입액을 포함하여 합산 연 900만 원이다.
- 근거: E-PENSION-LIMITS-D41

**문서 근거 요약**

- *E-PENSION-CREDIT-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/3` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금계좌는 납입하는 것만으로 세액공제 혜택이 있다.”
- *E-PENSION-LIMITS-D41** — [doc41.docx](https://drive.google.com/file/d/1KW188juCNeQYLxFVMIB6fAF7szwK-HIq/view)
- `#/texts/7` · label `text`
- 페이지 provenance 없음; `item_ref`와 아래 원본·Docling SHA로 고정
- source SHA-256 `40b4f60e717d2f72a3621e261b1659d1a05f793482537241c24ed77367939f03` · Docling JSON SHA-256 `eb71dee9b09dfe59d02f16b0f1848f1f329c686b5656ad214c405224d9c213c0`
- retrieval `knowledge-40b4f60e717d-0000`
- 인용: “연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. 그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. 세액공제 받을 수 있는 납입한도는 따로 정해져 있다. 연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다.”

**부족 근거·금지 주장**

- *부족 근거**
- • 소득공제 장기펀드의 종료 시점과 2026년 신규가입 가능 여부를 직접 확인할 최신 문서가 없다.
- *금지 주장**
- • 근거 없이 2015년 종료를 확정하지 않는다.
- • 과거 상품명 노출을 현재 판매 가능성으로 해석하지 않는다.
- *검토 메모**
- • 최신성 공백 판정은 적절하다. 세액공제 대상 여부와 한도는 C1·C2로 분리해 누락 평가가 가능하도록 수정했다.
- • 사람 검수 결과(수정 필요 → 수정 후 반영): 원칙 8은 "현재 세율과 세액공제 한도"를 최신성 확인 대상으로 명시하는데, 기존 답변은 소득공제 장기펀드의 최신성 공백만 명시하고 이어서 제시한 세액공제 한도(연 600만원·900만원)에는 "자료 작성 시점" 한정이 빠져 있어 현재도 그대로 유효한 수치처럼 읽힐 수 있었음. "자료 작성 시점 기준" 표현과 "2026년 현재도 그대로 적용되는지는 확인할 수 없다"는 문장을 추가함.

**검수 체크**

- [x] 질문 의도와 목표 답변이 맞다
- [x] 필수 주장이 답변에 빠짐없이 들어간다
- [x] 문서 근거가 충분하거나 부족 근거가 명확히 표시되어 있다
- [x] 금지 주장을 답변하지 않는다

**사람 검수 결과**

- 판정: [ ] OK  [x] 수정 필요  [ ] 보류
- 최종 반영 여부: [ ] 반영 불필요  [x] 수정 후 반영  [ ] 원문 확인 전 미반영
