from transformers import CanineTokenizer, CanineForTokenClassification, CanineForSequenceClassification
import torch
from collections import deque, Counter

batch_size = 128
truncation = 256

# NER 모델(CANINE)을 돌린 후 결과값을 return하는 함수
def ner_model(input :list) -> list:
    label_list = ['O', 'B-DT_DURATION', 'I-DT_DURATION', 'B-DT_DAY', 'I-DT_DAY', 'B-DT_WEEK', 'I-DT_WEEK', 'B-DT_MONTH',
                  'I-DT_MONTH', 'B-DT_YEAR', 'I-DT_YEAR', 'B-DT_SEASON', 'I-DT_SEASON', 'B-DT_OTHERS', 'I-DT_OTHERS',
                  'B-TI_DURATION', 'I-TI_DURATION', 'B-TI_HOUR', 'I-TI_HOUR', 'B-TI_MINUTE', 'I-TI_MINUTE', 'B-TI_OTHERS',
                  'I-TI_OTHERS', 'B-QT', 'I-QT']

    model_checkpoint = './checkpoint/checkpoint_NER'

    model = CanineForTokenClassification.from_pretrained(model_checkpoint)
    tokenizer = CanineTokenizer.from_pretrained(model_checkpoint)

    encoding = tokenizer(input, padding="max_length", truncation=True, max_length=truncation, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**encoding)  # forward pass

    logits = outputs.logits
    predictions = logits.argmax(-1)  # 가장 높은 logits값의 idx를 return

    true_predictions = [
        [label_list[p] for p in prediction if p != -100]
        for prediction in predictions
    ]

    final_preds = []
    for sent, label in zip(input, true_predictions):
        length = len(sent)
        final_preds.append((sent, label[1:length + 1]))

    return final_preds

# NER 결과를 후처리하는 함수
# return 형식 :  [[('주말', 'DT_DURATION'), ('오전', 'TI_DURATION')], [], ..., []] -> 문장 하나당 NER
def postprocess_NER(preds: list) -> list:
    # B,I를 기준으로 한 번 잘라줌
    deq = deque()
    final_ner = []
    for sent, label in preds:
        tmp = []
        former_tag = None
        for idx, tag in enumerate(label):
            if tag[0] == 'B':
                # 전 queue 비우기 & 추가
                ttmp = []
                while (deq):
                    ttmp.append(deq.popleft())
                if ttmp:
                    tmp.append(ttmp)
                deq.append((sent[idx], tag))

            elif tag[0] == 'I':
                # queue에 추가
                deq.append((sent[idx], tag))

            elif tag[0] == 'O' and deq:
                # queue 비우기
                ttmp = []
                while (deq):
                    ttmp.append(deq.popleft())
                if ttmp:
                    tmp.append(ttmp)

            elif idx == len(label) - 1 and tag[0] != 'O' and deq:
                # queue에 추가 뒤 비우기
                deq.append((sent[idx], tag))
                ttmp = []
                while (deq):
                    ttmp.append(deq.popleft())
                if ttmp:
                    tmp.append(ttmp)
            former_tag = tag

        final_ner.append(tmp)

    # 잘라져있는 값을 전처리 해줌
    integrated_ner = []
    for idx, sent in enumerate(final_ner):
        sent_ner = []
        for char_tag in sent:
            tmp_word = []
            tmp_ner_tag = []
            tmp_ner_BIO = []
            for char_text, tag in char_tag:
                tmp_word.append(char_text)
                tmp_ner_BIO.append(tag[:2])
                tmp_ner_tag.append(tag[2:])
            tmp_word = ''.join(tmp_word)
            tmp_ner_tag_set = list(set(tmp_ner_tag))
            tmp_ner_BIO = list(set(tmp_ner_BIO))

            # ner set의 평탄화(두개 이상의 tag가 올 시 하나로 바꿔준다.)
            if len(tmp_ner_tag_set) == 1:
                tmp_ner = tmp_ner_tag_set[0]
            else:
                if 'DT_OTHERS' in tmp_ner_tag_set:
                    tmp_ner = 'DT_OTHERS'
                elif 'TI_OTHERS' in tmp_ner_tag_set:
                    tmp_ner = 'TI_OTHERS'
                elif 'DT_DURATION' in tmp_ner_tag_set:
                    tmp_ner = 'DT_DURATION'
                elif 'TI_DURATION' in tmp_ner_tag_set:
                    tmp_ner = 'TI_DURATION'
                else:
                    # 과반수로 정한다.
                    tmp_ner = Counter(tmp_ner_tag).most_common(1)[0][0]

            # B-I 나 B 만 있는 tag들을 갖고 온다.
            if len(tmp_ner_BIO) == 2:
                # QT와 DT_SEASON을 제거한다.
                if tmp_ner != 'QT' and tmp_ner != 'DT_SEASON' and tmp_ner != 'TI_SECOND':
                    sent_ner.append((tmp_word, tmp_ner))
            elif len(tmp_ner_BIO) == 1 and tmp_ner_BIO[0][0] == 'B':
                if tmp_ner != 'QT' and tmp_ner != 'DT_SEASON' and tmp_ner != 'TI_SECOND':
                    sent_ner.append((tmp_word, tmp_ner))
            else:
                pass
                # print(idx)
                # print(tmp_word, tmp_ner)
                # print()

        integrated_ner.append(sent_ner)

    return integrated_ner

def intent_model(input :list) -> list:
    model_checkpoint_intent = './checkpoint/checkpoint_intent'

    model = CanineForSequenceClassification.from_pretrained(model_checkpoint_intent, num_labels=3)
    tokenizer = CanineTokenizer.from_pretrained(model_checkpoint_intent)

    encoding = tokenizer(input, padding="max_length", truncation=True, max_length=truncation, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**encoding)

    logits = outputs.logits
    predictions = logits.argmax(-1)
    intent_label_list = ['0', '+', '-']
    true_preds = [intent_label_list[x] for x in predictions]

    return true_preds

