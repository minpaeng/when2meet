import model
import definitions
import datetime as dt
import copy


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

    ######
    tmp_speakers = copy.deepcopy(definitions.speakers)

    for idx, speaker in enumerate(definitions.speakers.values()):
        if idx == 0:
            former = speaker
        else:
            former = former.intersection(speaker)

    ######
    return former, tmp_speakers


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

        self.str_year = str(self.year)
        # self.str_year = "0"*(len(self.str_year)-4) + self.str_year

        if self.month < 10:
            self.str_month = "0" + str(self.month)
        else:
            self.str_month = str(self.month)

        if self.day < 10:
            self.str_day = "0" + str(self.day)
        else:
            self.str_day = str(self.day)

        if self.begin_hour < 10:
            self.str_begin_hour = "0" + str(self.begin_hour)
        else:
            self.str_begin_hour = str(self.begin_hour)

        if self.begin_minute < 10:
            self.str_begin_minute = "0" + str(self.begin_minute)
        else:
            self.str_begin_minute = str(self.begin_minute)

        if self.end_hour < 10:
            self.str_end_hour = "0" + str(self.end_hour)
        else:
            self.str_end_hour = str(self.end_hour)

        if self.end_minute < 10:
            self.str_end_minute = "0" + str(self.end_minute)
        else:
            self.str_end_minute = str(self.end_minute)

    def __repr__(self):
        return f'{self.str_year}년 {self.str_month}월 {self.str_day}일 {self.str_begin_hour}:{self.str_begin_minute}~{self.str_end_hour}:{self.str_end_minute}'

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
    ######
    TODAY = dt.datetime.now()
    result, speakers = when_to_meet(dialogue)
    # person_ID, one_day
    # 1.없는 경우 = None -> 아예 리스트에 추가하지 않음
    # 2.다 되는 경우 = 현재 날짜(TODAY)로 부터 30일간을 다 넣어줌
    speakers_list = []

    # speakers = {name(person ID): person(When2meet 객체)}

    for name, person in speakers.items():
        if person.datetimes is None:  # 1.없는 경우 = None -> 아예 리스트에 추가하지 않음
            pass
        elif person.datetimes == []:  # 2.다 되는 경우 = 현재 날짜(TODAY)로 부터 30일간을 다 넣어줌
            person.final_set()
            for i in range(1, 31):
                # begin_DT, end_DT, begin_TI, end_TI = one_day
                t_d = TODAY + dt.timedelta(days=i)
                all_DT = definitions.Mydate(year=t_d.year, month=t_d.month, day=t_d.day)
                begin_TI = definitions.Mytime(hour=0)
                end_TI = definitions.Mytime(hour=24)
                tmp_one_day = One_day((all_DT, all_DT, begin_TI, end_TI))
                speakers_list.append({"name": name[1:], "date": tmp_one_day})

        else:  # 3. 해당 날짜만 되는 경우
            person.final_set()
            for one_datetime in person.datetimes:
                speakers_list.append({"name": name[1:], "date": One_day(one_datetime)})

    print("최종 화자들:", speakers_list)

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
