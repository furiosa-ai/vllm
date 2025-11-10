# ShareGPT Dataset 인자 변경 사항

## 개요
커밋 `1561cf7ec` 이후 ShareGPT 데이터셋에 입력/출력 길이를 정밀하게 제어하기 위한 4개의 새로운 인자가 추가되었습니다.

---

## 추가된 인자

### 1. `--sharegpt-target-total`
- **타입**: `int`
- **기본값**: `None`
- **설명**: 목표 전체 길이 (입력 + 출력)
- **용도**: `--sharegpt-target-output`과 함께 사용하여 요청을 필터링하고 정렬

### 2. `--sharegpt-target-output`
- **타입**: `int`
- **기본값**: `None`
- **설명**: 목표 출력 길이
- **용도**: `--sharegpt-target-total`과 함께 사용하여 필터링 범위 결정 및 실제 출력 길이 계산

### 3. `--sharegpt-enable-chat-template`
- **타입**: `bool` (action="store_true")
- **기본값**: `False`
- **설명**: Chat template overhead 계산 활성화
- **용도**: Chat template 사용 시 추가되는 토큰을 고려하여 입력 길이를 정확하게 필터링

### 4. `--sharegpt-output-adjustment`
- **타입**: `int`
- **기본값**: `0`
- **설명**: 입력에서 출력으로 토큰을 이동시키는 조정값
- **용도**: 양수 값 설정 시 입력 길이를 줄이고 출력 길이를 늘림 (전체 길이는 유지)

---

## 동작 원리

### 기본 필터링 로직 (adjustment = 0일 때)

```python
# 인자
target_total = 2048      # 전체 길이
target_output = 128      # 최소 출력 길이
output_adjustment = 0    # 조정값

# 필터 범위 계산
min_prompt_len = target_total - target_output - output_adjustment
               = 2048 - 128 - 0 = 1920

max_prompt_len = target_total
               = 2048

# 입력 범위: [1920, 2048]
# 출력 길이: target_total - effective_prompt_len

# 예시 케이스:
# 1) effective_prompt_len = 1920 → output = 2048 - 1920 = 128 (최대 출력)
# 2) effective_prompt_len = 2000 → output = 2048 - 2000 = 48
# 3) effective_prompt_len = 2048 → output = 2048 - 2048 = 0 (최소 출력)
```

**결과:**
- 입력: **1920 ~ 2048 토큰**
- 출력: **0 ~ 128 토큰** (최대 128)
- 전체: **2048 토큰**

---

### 조정값 사용 (adjustment = 128일 때)

```python
# 인자
target_total = 2048      # 전체 길이
target_output = 128      # 기본 출력 길이
output_adjustment = 128  # 조정값

# 필터 범위 계산
min_prompt_len = target_total - target_output - output_adjustment
               = 2048 - 128 - 128 = 1792

max_prompt_len = target_total
               = 2048

# 입력 범위: [1792, 2048] (256 토큰 범위)
# 출력 길이: target_total - effective_prompt_len

# 예시 케이스:
# 1) effective_prompt_len = 1792
#    → output = 2048 - 1792 = 256 (최대 출력)
#
# 2) effective_prompt_len = 1856
#    → output = 2048 - 1856 = 192
#
# 3) effective_prompt_len = 1920
#    → output = 2048 - 1920 = 128
#
# 4) effective_prompt_len = 2048
#    → output = 2048 - 2048 = 0 (최소 출력)
```

**결과:**
- 입력: **1792 ~ 2048 토큰** (256 토큰 범위)
- 출력: **0 ~ 256 토큰** (최대 256)
- 전체: 항상 **2048 토큰** (유지)

---

## Chat Template Overhead

`--sharegpt-enable-chat-template` 활성화 시:

1. **Overhead 계산**:
   ```python
   empty_template = tokenizer.apply_chat_template(
       [{"role": "user", "content": ""}],
       tokenize=False,
       add_generation_prompt=True
   )
   chat_template_overhead = len(tokenizer.encode(empty_template))
   ```

2. **유효 입력 길이 조정**:
   ```python
   effective_prompt_len = prompt_len + chat_template_overhead
   ```

3. **필터링**: `effective_prompt_len`을 기준으로 필터링 수행

**예시:**
- `chat_template_overhead = 10 토큰`
- `prompt_len = 1910 토큰`
- `effective_prompt_len = 1910 + 10 = 1920 토큰`
- 필터 범위 `[1792, 1920]`에 포함되므로 통과

---

## 추가된 기능

### 1. 샘플 정렬
`target_total`과 `target_output`이 설정되면:
- 필터링된 샘플을 **입력 길이 기준 오름차순 정렬**
- 짧은 입력 → 긴 출력 순서로 배치

### 2. 성능 최적화
- `target_total`/`target_output` 사용 시 completion을 토크나이즈하지 않음
- 불필요한 계산 제거로 데이터셋 로딩 속도 향상

### 3. 디버깅 로그
```python
print(f"Chat template overhead: {chat_template_overhead} tokens")
print(f"Processed {processed_count} entries, collected {len(samples)} samples")
```

---

## 사용 예시

### 예시 1: 기본 사용 (입력 1920~2048, 출력 0~128)
```bash
python -m vllm.entrypoints.cli.main bench serve \
    --backend "vllm" \
    --model "LGAI-EXAONE/EXAONE-3.5-32B-Instruct" \
    --dataset-name "sharegpt" \
    --dataset-path "./ShareGPT_V3_unfiltered_cleaned_split.json" \
    --sharegpt-target-total 2048 \
    --sharegpt-target-output 128
```
- **입력**: 1920 ~ 2048 토큰
- **출력**: 0 ~ 128 토큰 (최대 128)
- **전체**: 2048 토큰

---

### 예시 2: 출력 조정 (입력 1792~2048, 출력 0~256)
```bash
python -m vllm.entrypoints.cli.main bench serve \
    --backend "vllm" \
    --model "LGAI-EXAONE/EXAONE-3.5-32B-Instruct" \
    --dataset-name "sharegpt" \
    --dataset-path "./ShareGPT_V3_unfiltered_cleaned_split.json" \
    --sharegpt-target-total 2048 \
    --sharegpt-target-output 128 \
    --sharegpt-output-adjustment 128
```
- **입력**: 1792 ~ 2048 토큰 (256 토큰 범위)
- **출력**: 0 ~ 256 토큰 (최대 256)
- **전체**: 정확히 2048 토큰

---

### 예시 3: Chat Template 사용
```bash
python -m vllm.entrypoints.cli.main bench serve \
    --backend "vllm" \
    --model "LGAI-EXAONE/EXAONE-3.5-32B-Instruct" \
    --dataset-name "sharegpt" \
    --dataset-path "./ShareGPT_V3_unfiltered_cleaned_split.json" \
    --sharegpt-target-total 1024 \
    --sharegpt-target-output 128 \
    --sharegpt-enable-chat-template \
    --sharegpt-output-adjustment 32 \
    --endpoint "/v1/completions"
```
- **Chat template overhead**: 자동 계산 (예: 10 토큰)
- **입력 범위**: `[1024 - 128 - 32, 1024]` = `[864, 1024]` (유효 길이 기준)
- **실제 프롬프트**: 854 ~ 1014 토큰 (overhead 10 제외)
- **출력**: 0 ~ 160 토큰
- **전체**: 정확히 1024 토큰

---

## 수식 요약

```python
# 인자
T = target_total          # 전체 목표 길이
O = target_output         # 기본 출력 길이
A = output_adjustment     # 조정값
C = chat_template_overhead  # Chat template overhead (활성화 시)

# 필터 범위
min_prompt = T - O - A
max_prompt = T - O

# 유효 입력 길이
effective_prompt = prompt_len + C  # (enable_chat_template=True일 때)

# 필터 조건
min_prompt ≤ effective_prompt ≤ max_prompt

# 실제 출력 길이
output_len = T - effective_prompt

# 전체 길이 (항상 유지)
total = effective_prompt + output_len = T
```

---

## 디코딩 기대 횟수

각 샘플은:
1. **입력 토큰**: 필터 범위 내에서 선택됨
2. **디코딩 횟수**: `output_len`번 (= `target_total - effective_prompt_len`)

### 예시 계산 (adjustment = 128 사용 시)

| 입력 길이 | 출력 길이 | 디코딩 횟수 | 전체 길이 |
|----------|----------|-----------|----------|
| 1792     | 256      | 256회     | 2048     |
| 1856     | 192      | 192회     | 2048     |
| 1920     | 128      | 128회     | 2048     |

**평균 디코딩 횟수**: `(256 + 128) / 2 = 192회` (입력이 균등 분포라고 가정)

---

## 주의사항

1. **전체 길이 유지**:
   - `output_adjustment`는 입력/출력 비율만 조정
   - 전체 길이는 항상 `target_total`로 유지됨

2. **최소 출력 보장**:
   - 출력은 최소 `target_output` 토큰 이상 보장
   - `output_adjustment`만큼 더 늘어날 수 있음

3. **Chat Template**:
   - `--sharegpt-enable-chat-template` 사용 시 overhead가 자동 계산됨
   - 실제 프롬프트 길이보다 유효 길이가 더 길어질 수 있음

4. **샘플 부족 가능성**:
   - 필터 범위가 좁으면 샘플이 부족할 수 있음
   - `Processed X entries, collected Y samples` 로그로 확인 필요
