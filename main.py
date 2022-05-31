import model
import definitions
import datetime as dt


def when_to_meet(data, today=dt.datetime.now()):
    def check_person(data: list):
        persons = [x['person'] for x in data]
        persons = list(set(persons))
        persons.sort()
        return persons

    definitions.TODAY = today
    persons_name = check_person(data)
    # 전체 총괄 객체(전체 default값 저장용도)
    definitions.summarization = definitions.Summarization()
    # When2meet 객체들을 사람수만큼 정의해준다. 맨 처음 대화가 들어왔을 때 생성된다.
    definitions.persons = [definitions.When2meet(x) for x in persons_name]

    # 상호작용하는데 필요하여 name을 가지고 dict으로 묶어준다.
    definitions.speakers = {name: person for name, person in zip(persons_name, definitions.persons)}
    for sent in data:
        if sent['intent'] != '0':
            one_sch = definitions.Schedule(sent['ner'], sent['intent'], sent['person'])
            if sent['ner']:
                if sent['intent'] == '+':
                    definitions.speakers[sent['person']] + one_sch
                elif sent['intent'] == '-':
                    definitions.speakers[sent['person']] - one_sch

    for idx, speaker in enumerate(definitions.speakers.values()):
        if idx == 0:
            former = speaker
        else:
            former = former.intersection(speaker)

    return former


class One_day():
    def __init__(self, one_day):
        begin_DT, end_DT, begin_TI, end_TI = one_day
        self.year = begin_DT.year
        self.month = begin_DT.month
        self.day = begin_DT.day
        self.begin_hour = begin_TI.hour
        self.begin_minute = begin_TI.minute
        self.end_hour = end_TI.hour
        self.end_minute = end_TI.minute
        self.sum = self.year * (10 ** 8) + self.month * (10 ** 6) + self.day * (10 ** 4) + self.begin_hour * (
                    10 ** 2) + self.begin_minute

    def __repr__(self):
        return f'{self.year}년 {self.month}월 {self.day}일 {self.begin_hour}:{self.begin_minute}~{self.end_hour}:{self.end_minute}'

    def __lt__(self, other):
        return self.sum < other.sum

    def __le__(self, other):
        return self.sum <= other.sum

    def __gt__(self, other):
        return self.sum > other.sum

    def __ge__(self, other):
        return self.sum <= other.sum

    def __eq__(self, other):
        return self.sum == other.sum


if __name__ == "__main__":
    inputs = ['우리 언제 만나냐',
              '담주에 저녁먹을래?',
              '오오 만나자',
              'ㅠㅠㅠ 만나줘 제발',
              'ㅋㅋㅋㅋㅋㅋ다들 바쁜것 같아서ㅜ',
              '노노 하나도 안바빠',
              '마침 요즘 할일 없어서 심심했음',
              '다들 잘지냈냐',
              '오 오랜만이여',
              'ㅋㅋㅋㅋㅋㅎㅇㅎㅇ',
              '나 담주 화수목 저녁에 되는디',
              '아님 주말 오전에 돼',
              '난 담주 수요일이랑 토요일 가능해여~',
              '아 난 주말은 안될듯ㅜㅜ',
              '뭐 어쩔 수 없제',
              '난 다음 주 오후에는 다 가능~']

    inputs_person = ['P1',
                     'P2',
                     'P3',
                     'P4',
                     'P4',
                     'P1',
                     'P2',
                     'P3',
                     'P2',
                     'P2',
                     'P3',
                     'P3']

    # ner 추출
    ner = model.ner_model(inputs)
    ner = model.postprocess_NER(ner)
    print(len(inputs), len(ner))
    print(ner)

    # intent 추출
    intent = model.intent_model(inputs)
    print(intent)

    dialogue = [{'person': one_person, 'ner': one_ner, 'intent': one_intent} for one_person, one_ner, one_intent in
                zip(inputs_person, ner, intent)]
    result = when_to_meet(dialogue)

    print()
    print("<결과>")
    result = result.datetimes
    if result is None:
        print("다같이 만날 수 있는 시간 존재x")
    elif result is []:
        print("모두 만날 수 있음")
    else:
        tmp = []
        for one_datetime in result:
            tmp.append(One_day(one_datetime))
        result = tmp
        result.sort()
        print(result)
