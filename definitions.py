import re
import copy
from itertools import product
from collections import deque
import datetime as dt


stopword = ['쯤', '쯔음', '즈음', '정도', '때', '약', '대략', '안팎']
# 여(두달'여'동안), 한(한 두달부터)

# 기간 = 시점 + 부사 + 불용어 라고 판단. 그 부사들의 리스트
dt_duration = ['~', '부터', '까지', '부턴', '까진', '이상', '이후', '이전', '이내', '중순', '에서', '에선','사이', '마다',
               '내내', '동안', '가량', '내', '초', '말', '중', '전', '뒤', '안', '후', '간']  # 긴 글자가 먼저 찾아지게

# 추가적인 의미를 더해준다. 불용어는 아닌, 부사들보다는 덜하지만 추가적인 의미를 더해주는 말들
additional_adv = ['지난', '오는', '주말', '내일']  # , '하루종일'

ti_stopword = ['쯤', '쯔음', '즈음', '정도', '때', '약', '대략', '안팎', '경', '정각']
ti_additional_adv = ['오전', '오후']
# 기간 = 시점 + 부사 + 불용어 라고 판단. 그 부사들의 리스트
ti_duration = ['~', '부터', '까지', '부턴', '까진',  '이상', '이후', '이전', '이내', '에서', '사이', '마다',
               '내내', '동안', '가량', '전', '후', '내', '중', '뒤', '안']  # 긴 글자가 먼저 찾아지게

TODAY = dt.datetime.today()

# word가 시점인지 기간인지를 판단하는 함수
# 기준: Label로 구분, but others의 경우 섞여 있어 정규표현식으로 걸러내야 함.

def classify_point_TI(wordNner):
    word, ner = wordNner
    result = {'word': word, 'ner': ner, 'durNpoint': None, 'parsing': []}

    # 1.기본적인 불용어 제거
    for sw in ti_stopword:
        if sw in word:
            word = word.replace(sw, '')
    word = word.strip()

    # 2.추가적인 부사 제거 -> 부사의 우선순위를 정할 필요가 없는 것들
    def parse_add_adv(word):
        add_list = []
        for adv in ti_additional_adv:
            if adv in word:
                p = re.compile(adv)
                tmp_index = list(p.finditer(word))
                for one in tmp_index:
                    add_list.append(one.span())

        result = []
        former = 0

        if add_list:
            add_list.sort()

            for begin, end in add_list:
                result.append((word[former:begin].strip(), None))  # 정해지지 않음
                result.append((word[begin:end].strip(), True))  # 다시 한번
                former = end

            if len(word) != end:
                result.append((word[end:].strip(), None))  # 정해지지 않음

            result = [x for x in result if x[0]]
            for i in ti_additional_adv:
                word = word.replace(i, '')
        else:
            result.append((word, None))

        word = re.sub('[ ]+', ' ', word.strip())

        return word, result

    word, parsing = parse_add_adv(word)

    # parsing = [(word, None)]
    # 3. 기간 부사 제거
    # DT_OTHERS: 기간>시점일 때 - 부사 리스트 안에 단어가 있는지 판단을 통해 분류
    def parse_dur(parsing):
        def search_long_index(index_list):
            overlap = []
            no_overlap = []

            count = 0
            for idx, (begin, end) in enumerate(index_list):
                if idx == (len(index_list) - 1):
                    if count == 0:
                        no_overlap.append((begin, end))
                else:
                    after_begin, after_end = index_list[idx + 1][0], index_list[idx + 1][1]
                    if begin <= after_begin and end >= after_end:
                        overlap.append((begin, end))
                        count += 1
                    elif after_begin <= begin and after_end >= end:
                        overlap.append((after_begin, after_end))
                        count += 1
                    else:
                        if count == 0:
                            no_overlap.append((begin, end))
                        count = 0

            no_overlap += overlap
            no_overlap = list(set(no_overlap))
            no_overlap.sort()

            return no_overlap

        parsing2 = []

        for idx, (word, flag) in enumerate(parsing):
            count = 0  # parsing의 부사 갯수
            if flag == None:
                # 부사에 대해 파싱을 진행
                index_list = []
                # word 하나에 부사가 있는지 확인 한 후 index_list로 뽑아준다.
                for idx, dur in enumerate(ti_duration):
                    if dur in word:
                        p = re.compile(dur)
                        tmp_index = list(p.finditer(word))
                        for one in tmp_index:
                            index_list.append(one.span())

                # 기존의 index와 겹치는 것(길이 동안 > 안)이 있다면 추가하지 않게
                if index_list:
                    index_list.sort()
                    index_list = search_long_index(index_list)
                    count += len(index_list)

                    former = 0

                    for begin, end in index_list:
                        parsing2.append((word[former:begin].strip(), True))  # 정해지지 않음
                        ###################
                        w_ = word[begin:end].strip()
                        parsing2.append((w_, False, ti_duration.index(w_)))  # 부사가 아닌 걸로 정해짐
                        former = end
                    if len(word) != end:
                        parsing2.append((word[end:].strip(), True))  # 정해지지 않음

                    for i in ti_duration:
                        word = word.replace(i, '')
                    word = re.sub('[ ]+', ' ', word.strip())


                # 그대로 parsing2에 word를 True로 추가
                else:
                    parsing2.append((word, True))

            else:
                # flag가 False/True일 때 = 그대로 추가
                parsing2.append((word, flag))
        parsing2 = [x for x in parsing2 if x[0]]

        if count:
            return word, (parsing2, 'DUR', count)
        else:
            return word, (parsing2, 'POINT', count)

    ############## DT-DURATION'8-9일동안'/'8~9일동안'/'수~목요일동안' 이런 문제는 NEN으로 해결가능한가?
    #### 같이 들어오는 부사들 '부터~까지'는 생략이 되지 않는다면 가능하긴 할 것이다.....생성으로 가야겟네
    word, (result['parsing'], result['durNpoint'], dur_count) = parse_dur(parsing)
    return result


# word가 시점인지 기간인지를 판단하는 함수
# 기준: Label로 구분, but others의 경우 섞여 있어 정규표현식으로 걸러내야 함.

def classify_point(wordNner):
    word, ner = wordNner
    result = {'word': word, 'ner': ner, 'durNpoint': None, 'parsing': []}

    # 1.기본적인 불용어 제거
    for sw in stopword:
        if sw in word:
            word = word.replace(sw, '')
    word = word.strip()

    # 2.추가적인 부사 제거 -> 부사의 우선순위를 정할 필요가 없는 것들
    def parse_add_adv(word):
        add_list = []
        for adv in additional_adv:
            if adv in word:
                p = re.compile(adv)
                tmp_index = list(p.finditer(word))
                for one in tmp_index:
                    add_list.append(one.span())

        result = []
        former = 0

        if add_list:
            add_list.sort()

            for begin, end in add_list:
                result.append((word[former:begin].strip(), None))  # 정해지지 않음

                #                 result.append((word[begin:end].strip(), False)) # 추가부사로 정해짐
                #                 result.append((word[begin:end].strip(), None)) # 추가부사로 정해짐
                result.append((word[begin:end].strip(), True))  # 추가부사로 정해짐
                former = end

            if len(word) != end:
                result.append((word[end:].strip(), None))  # 정해지지 않음

            result = [x for x in result if x[0]]
            for i in additional_adv:
                word = word.replace(i, '')
        else:
            result.append((word, None))

        word = re.sub('[ ]+', ' ', word.strip())

        return word, result

    word, parsing = parse_add_adv(word)

    # parsing = [(word, None)]
    # 3. 기간 부사 제거
    # DT_OTHERS: 기간>시점일 때 - 부사 리스트 안에 단어가 있는지 판단을 통해 분류
    def parse_dur(parsing):
        def search_long_index(index_list):
            overlap = []
            no_overlap = []

            count = 0
            for idx, (begin, end) in enumerate(index_list):
                if idx == (len(index_list) - 1):
                    if count == 0:
                        no_overlap.append((begin, end))
                else:
                    after_begin, after_end = index_list[idx + 1][0], index_list[idx + 1][1]
                    if begin <= after_begin and end >= after_end:
                        overlap.append((begin, end))
                        count += 1
                    elif after_begin <= begin and after_end >= end:
                        overlap.append((after_begin, after_end))
                        count += 1
                    else:
                        if count == 0:
                            no_overlap.append((begin, end))
                        count = 0

            no_overlap += overlap
            no_overlap = list(set(no_overlap))
            no_overlap.sort()

            return no_overlap

        parsing2 = []

        for idx, (word, flag) in enumerate(parsing):
            count = 0  # parsing의 부사 갯수
            if flag == None:
                # 부사에 대해 파싱을 진행
                index_list = []
                # word 하나에 부사가 있는지 확인 한 후 index_list로 뽑아준다.
                for idx, dur in enumerate(dt_duration):
                    if dur in word:
                        p = re.compile(dur)
                        tmp_index = list(p.finditer(word))
                        for one in tmp_index:
                            index_list.append(one.span())

                # 기존의 index와 겹치는 것(길이 동안 > 안)이 있다면 추가하지 않게
                if index_list:
                    index_list.sort()
                    index_list = search_long_index(index_list)
                    count += len(index_list)

                    former = 0

                    for begin, end in index_list:
                        parsing2.append((word[former:begin].strip(), True))  # 정해지지 않음
                        ###################
                        w_ = word[begin:end].strip()
                        parsing2.append((w_, False, dt_duration.index(w_)))  # 부사가 아닌 걸로 정해짐
                        former = end
                    if len(word) != end:
                        parsing2.append((word[end:].strip(), True))  # 정해지지 않음

                    for i in dt_duration:
                        word = word.replace(i, '')
                    word = re.sub('[ ]+', ' ', word.strip())


                # 그대로 parsing2에 word를 True로 추가
                else:
                    parsing2.append((word, True))

            else:
                # flag가 False/True일 때 = 그대로 추가
                parsing2.append((word, flag))
        parsing2 = [x for x in parsing2 if x[0]]

        if count:
            return word, (parsing2, 'DUR', count)
        else:
            return word, (parsing2, 'POINT', count)

    ############## DT-DURATION'8-9일동안'/'8~9일동안'/'수~목요일동안' 이런 문제는 NEN으로 해결가능한가?
    #### 같이 들어오는 부사들 '부터~까지'는 생략이 되지 않는다면 가능하긴 할 것이다.....생성으로 가야겟네
    word, (result['parsing'], result['durNpoint'], dur_count) = parse_dur(parsing)
    return result


# 상대적인지 절대적인지(=현재 날짜를 기준으로 더해야하는지, 바로 설정해야하는지)를 판단하는 함수
# 기준: 숫자가 들어갔는지 안들어갔는지로 판단. 한글화 된 숫자를 포함하여 정규표현식으로 걸러내야 함.
# 1. 숫자가 들어갔는가?
# 2. 숫자가 들어가지 않았더라도 한글로 표현이 된 숫자인가?
# 3. 같이 들어가 있을 때는?

# 위에서 파싱되서 POINT로 들어간다고 가정한다.
# 해당 되지 않는 tag안의 단어들은 모두 삭제한다. ex) 올해 2022년 -> 2022년

# 결국에는 OTHERS와 DURATION의 특정 format, 용어들을 남겨놓고 해야한다.
# 숫자만 남아있는 경우는 자리나 앞에서 나온 값의 연장일 것이다. 맨 마지막으로 빼야 됨.

def classify_abs(total_word: dict):
    word, ner, durNpoint, parsing = total_word['word'], total_word['ner'], total_word['durNpoint'], total_word[
        'parsing']
    final_parsing = []

    def matchNparse(words, pattern, label, rel_or_abs, idx):
        # 해당 단어와 매치되는지 판단해주고, 매치된다면 해당 단어를 파싱해주는 함수
        # 파싱이 되지 않은 값들은 None이고, 된다면 True가 된다.
        # pattern 하나에 대해서 단어들을 찾음
        parsing_list = []
        p = re.compile(pattern)
        for word in words:
            flag = word[1]
            if flag == None:
                w = word[0]
                index_list = list(p.finditer(w))
                index_list = [one.span() for one in index_list]
                former = 0
                # 찾았다면
                if index_list:
                    for begin, end in index_list:
                        parsing_list.append((w[former:begin].strip(), None))  # 정해지지 않음
                        parsing_list.append((w[begin:end].strip(), True, label, rel_or_abs, idx))  # 추가부사로 정해짐
                        former = end
                    if len(w) != end:
                        parsing_list.append((w[end:].strip(), None))  # 정해지지 않음

                # 찾지 못했다면 그대로 추가
                else:
                    parsing_list.append(word)

            elif flag == True:
                parsing_list.append(word)

            else:
                raise Exception(f'이상한 label 들어옴:{words}')

        parsing_list = [one for one in parsing_list if one[0]]
        return parsing_list

    for word in parsing:
        #  True라면 select후 parsing
        if word[1]:
            parsing_word = [(word[0], None)]
            dt_relative_year = ['올해|이번 ?년도?|이번 ?해']  # 나머지는 굳이 안봐도 될거라고 판단
            dt_absolute_year = ['[1-2][0-9][0-9][0-9]년']  # 숫자가 있을 때에는 '올해','지난' 빼기 -> 2018년올해/지난 2015년 경우임

            dt_relative_month = ['그 ?달', '다*담 ?달|다*다음 ?달', '내달|당월|이 ?달|이번 ?달',
                                 '열?[한두세네] ?달|열 ?달|다섯 ?달|여섯 ?달|일곱 ?달|여덟 ?달|아홉 ?달', '[0-9]+달']  # 수량은 부사랑 같이옴 ex)두달뒤
            dt_absolute_month = ['막 ?달|마지막 ?달', '[0-2]?[0-9]월', '십?[일이삼사오육유칠팔구십] ?월']  ### 일월, 일 월, 이월 ,이 월... 추가하기

            dt_relative_week = ['다*담 ?주|다*다음 ?주', '이번 ?주', '[0-9]?[0-9]주', '[일이삼사오]주일?', '한주']

            dt_absolute_week = ['첫 ?주', '막 ?주|마지막 ?주', '[첫둘셋넷][째쨋] ?주|다섯[째쨋] ?주',
                                '[0-9]째주', '[첫두세네]번째 ?주|다섯번째 ?주']  # 'N,N째주'도 고려해야됨
            dt_relative_day = ['내일|낼', '하루|[이2]틀|모레|글피|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘',
                               '오늘|당일', '다음 ?날|담 ?날', '[첫둘셋넷]째 ?날|다섯째 ?날', '[첫두세네]번째 ?날|다섯번째 ?날',
                               '[월화수목금토일]욜날?|[월화수목금토일](요일)날?', '[월화수목금토]']  # 일(요일) 어떻게? ,
            dt_absolute_day = ['[0-3]?[0-9](일날?)', '[이삼]?[십]?[일이삼사오육칠팔구십] ?일']  # 온갖 공휴일

            dt_relative_duration = ['평일', '주말']
            # 특정 숫자 format들
            dt_absolute_others = ['[1-2][0-9][0-9][0-9]/[0-1]?[0-9]/[0-3]?[0-9]|[0-1]?[0-9]/[0-3]?[0-9]',
                                  # 2022/2/14  02/14
                                  '[1-2][0-9][0-9][0-9]-[0-1]?[0-9]-[0-3]?[0-9]',
                                  # 2022-02-4   2-4 헷갈릴수 있어 뺌  # [0-1]?[0-9]-[0-3]?[0-9]
                                  '[1-2][0-9][0-9][0-9]\.[0-1]?[0-9]\.[0-3]?[0-9]|[0-1]?[0-9]\.[0-3]?[0-9]']  # 2012.12.12

            dt_relative_others = []  # 흠... 추가로 NER을 돌려야 할 것 같다.
            dt_absolute_duration = []

            dt_final_adv = [('일', 'DT_DAY', 'REL', 7), ('[0-9][0-9][0-9][0-9][0-9][0-9]', 'DT_OTHERS', 'ABS', 3),
                            ('[0-9][0-9][0-9][0-9]', 'DT_OTHERS', 'ABS', 4), ('[0-9]?[0-9]', 'DT_DAY', 'ABS', 2)]

            all_point = [(dt_relative_year, dt_absolute_year), (dt_relative_month, dt_absolute_month),
                         (dt_relative_week, dt_absolute_week), (dt_relative_day, dt_absolute_day)]
            dt_point = ['DT_YEAR', 'DT_MONTH', 'DT_WEEK', 'DT_DAY']

            # YEAR/MONTH/WEEK/DAY라면 단순 매치 후 파싱, 그리고 태그해준다. 남는 단어는 불용어라 판단, None으로 태그해준다.
            if ner == 'DT_YEAR':
                for idx, pattern in enumerate(dt_relative_year):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_YEAR', 'REL', idx)

                for idx, pattern in enumerate(dt_absolute_year):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_YEAR', 'ABS', idx)


            elif ner == 'DT_MONTH':
                for idx, pattern in enumerate(dt_relative_month):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_MONTH', 'REL', idx)

                for idx, pattern in enumerate(dt_absolute_month):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_MONTH', 'ABS', idx)


            elif ner == 'DT_WEEK':
                for idx, pattern in enumerate(dt_relative_week):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_WEEK', 'REL', idx)

                for idx, pattern in enumerate(dt_absolute_week):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_WEEK', 'ABS', idx)


            elif ner == 'DT_DAY':

                for idx, pattern in enumerate(dt_relative_day):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_DAY', 'REL', idx)

                for idx, pattern in enumerate(dt_absolute_day):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_DAY', 'ABS', idx)


            # 한번 더 NER model을 돌려 자동으로 분석되게 하든지 rule-based로 짜든지 해야한다. 일단은 rule-based로 진행한다.

            # DUR/OTHERS라면 매치가 되면 파싱 후 태그해준다. 그리고 남는 단어는 일단 True로 태그후,
            # 정규표현식으로 다시 한번 걸러 파싱 후 태그, 그리고 남는 단어는 None으로 태그해준다.

            elif ner == 'DT_DURATION' or 'DT_OTHERS':
                for idx, pattern in enumerate(dt_relative_duration):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_DURATION', 'REL', idx)

                for idx, pattern in enumerate(dt_absolute_others):
                    parsing_word = matchNparse(parsing_word, pattern, 'DT_OTHERS', 'ABS', idx)

                for i, (rel_label, abs_label) in enumerate(all_point):  # class label dt_point[i]
                    for idx, pattern in enumerate(rel_label):
                        parsing_word = matchNparse(parsing_word, pattern, dt_point[i], 'REL', idx)
                    for idx, pattern in enumerate(abs_label):
                        parsing_word = matchNparse(parsing_word, pattern, dt_point[i], 'ABS', idx)

            else:
                raise Exception(f'이상한 label 들어옴:{word}')

            # 추가 라벨 파싱
            for pattern, classlabel, relORabs, idx in dt_final_adv:
                parsing_word = matchNparse(parsing_word, pattern, classlabel, relORabs, idx)
            final_parsing += parsing_word

        # False라면 그대로 추가
        else:
            final_parsing.append(word)

    total_word['parsing'] = final_parsing

    return total_word


def classify_TI(total_word: dict):
    word, ner, durNpoint, parsing = total_word['word'], total_word['ner'], total_word['durNpoint'], total_word[
        'parsing']
    final_parsing = []

    def matchNparse(words, pattern, label, idx):
        # 해당 단어와 매치되는지 판단해주고, 매치된다면 해당 단어를 파싱해주는 함수
        # 파싱이 되지 않은 값들은 None이고, 된다면 True가 된다.
        # pattern 하나에 대해서 단어들을 찾음
        parsing_list = []
        p = re.compile(pattern)
        for word in words:
            flag = word[1]
            if flag == None:
                w = word[0]
                index_list = list(p.finditer(w))
                index_list = [one.span() for one in index_list]
                former = 0
                # 찾았다면
                if index_list:
                    for begin, end in index_list:
                        parsing_list.append((w[former:begin].strip(), None))  # 정해지지 않음
                        parsing_list.append((w[begin:end].strip(), True, label, idx))
                        former = end
                    if len(w) != end:
                        parsing_list.append((w[end:].strip(), None))  # 정해지지 않음

                # 찾지 못했다면 그대로 추가
                else:
                    parsing_list.append(word)

            elif flag == True:
                parsing_list.append(word)

            else:
                raise Exception(f'이상한 label 들어옴:{words}')

        parsing_list = [one for one in parsing_list if one[0]]
        return parsing_list

    for word in parsing:
        # True라면 select후 parsing
        if word[1]:
            parsing_word = [(word[0], None)]
            duration = ['오전|오후|AM|PM|am|pm', '아침|점심|저녁|새벽|낮|밤']

            hour = ['정오|자정', '[0-2]?[0-9]시간', '[0-2]?[0-9]시', '[한두세네]시간',
                    '열?[한두세네] ?시|열?다섯 ?시|열?여섯 ?시|열?일곱 ?시|열?여덟 ?시|열?아홉 ?시|열 ?시',
                    '십?[일이삼사오육칠팔구] ?시|이십[일이]? 시']

            minute = ['반', '[0-6]?[0-9]분', '[이삼사오육]?십? ?[일이삼사오육칠팔구]? ?분']

            # 특정 숫자 format
            others = ['[0-9]?[0-9]:[0-9]?[0-9]', '[0-9]?[0-9]:[0-9]?[0-9]:[0-9]?[0-9]']

            all_point = [hour, minute]
            ti_point = ['TI_HOUR', 'TI_MINUTE']

            # YEAR/MONTH/WEEK/DAY라면 단순 매치 후 파싱, 그리고 태그해준다. 남는 단어는 불용어라 판단, None으로 태그해준다.
            if ner == 'TI_HOUR':
                for idx, pattern in enumerate(duration):
                    parsing_word = matchNparse(parsing_word, pattern, 'TI_DURATION', idx)

                for idx, pattern in enumerate(hour):
                    parsing_word = matchNparse(parsing_word, pattern, 'TI_HOUR', idx)

            elif ner == 'TI_MINUTE':
                for idx, pattern in enumerate(minute):
                    parsing_word = matchNparse(parsing_word, pattern, 'TI_MINUTE', idx)


            elif ner == 'TI_DURATION' or 'TI_OTHERS':
                for idx, pattern in enumerate(duration):
                    parsing_word = matchNparse(parsing_word, pattern, 'TI_DURATION', idx)

                for idx, pattern in enumerate(others):
                    parsing_word = matchNparse(parsing_word, pattern, 'TI_OTHERS', idx)

                for i, point_class in enumerate(all_point):  # class label dt_point[i]
                    for idx, pattern in enumerate(point_class):
                        parsing_word = matchNparse(parsing_word, pattern, ti_point[i], idx)

            else:
                raise Exception(f'이상한 label 들어옴:{word}')

            # 추가 라벨 파싱
            #             for pattern, classlabel, relORabs, idx in dt_final_adv:
            #                 parsing_word = matchNparse(parsing_word,pattern,classlabel,relORabs,idx)
            final_parsing += parsing_word

        # False라면 그대로 추가
        else:
            final_parsing.append(word)

    total_word['parsing'] = final_parsing

    return total_word


def ordinal_number(kr_number: str):  # 서수
    kr_DT = {'일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9, '십': 10}
    kr_number = kr_number.strip()
    n = 0
    # 해봤자 ()십()
    length = len(kr_number)
    if length == 1:  # 일이삼사오육칠팔구십
        n = kr_DT[kr_number]

    elif length == 2:  # 십일 십이 ... 이십, 삼십, 사십, 오십, 육십
        if kr_number[0] == '십':
            n = kr_DT[kr_number[0]] + kr_DT[kr_number[1]]
        else:
            n = kr_DT[kr_number[0]] * kr_DT[kr_number[1]]
        return n

    elif length == 3:  # 이십일 이십이 .. 삼십일 .. 삽
        n = kr_DT[kr_number[0]] * kr_DT[kr_number[1]] + kr_DT[kr_number[2]]
    return n


def ordinal_number2(kr_number: str):  # 서수
    number_list = {'첫': 1, '둘': 2, '두': 2, '셋': 3, '세': 3, '넷': 4, '네': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9,
                   '열': 10}
    for ord_num in number_list:
        if ord_num in kr_number:
            return number_list[ord_num]


def cardinal_number(kr_number: str):
    kr_TI = {'한': 1, '두': 2, '세': 3, '네': 4, '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10, '열한': 11, '열두': 12,
             '열세': 13, '열네': 14, '열다섯': 15, '열여섯': 16, '열일곱': 17, '열여덟': 18, '열아홉': 19}
    for car_num in reversed(kr_TI.keys()):
        if car_num in kr_number:
            return kr_TI[car_num]

class Summarization():
    def __init__(self):
        # DT
        self.year = False
        self.month = False
        self.week = False
        self.day = False
        self.DT_list = [self.year, self.month, self.week, self.day]
        # TI
        self.hour = False
        self.minute = False

        self.flag_year = False
        self.flag_month = False
        self.flag_week = False
        self.flag_day = False
        self.all_flag_list = [self.flag_year, self.flag_month, self.flag_week, self.flag_day]

    def __repr__(self):
        return f'Summarization:[year:{self.year}, month:{self.month}, week:{self.week}, day:{self.day}, hour:{self.hour}, minute:{self.minute}]'

    #     def return_upper_default(self):
    #         if self.flag_week:
    #             return 2
    #         elif self.flag_month:
    #             return 1
    #         elif self.flag_day:
    #             return (self.month, self.day)
    #         else:
    #             return 0

    def return_flag_default(self):
        if self.flag_year:  # year이 설정되어(=다 되어) 있을 때
            return 0
        elif self.flag_month:  # month
            return 1
        elif self.flag_week:
            return 2
        elif self.flag_day:
            return 3
        else:
            print('error! 다 되어 있는데?')
            return None

    def set_default_DT(self, idx: int, number):
        if idx == 0:
            if not self.year:
                self.year = number
            elif self.year < number:
                self.year = number
            self.flag_year = True

        elif idx == 1:
            if not self.month:
                self.month = number
            elif self.month < number:
                pass
            #                 self.month = number
            self.flag_month = True

        elif idx == 2:
            if not self.week:
                self.week = number
            elif self.week < number:
                self.week = number
            self.flag_week = True

        elif idx == 3:
            if not self.day:
                self.day = number
            elif self.day > number:
                self.day = number
            self.flag_day = True

        self.DT_list = [self.year, self.month, self.week, self.day]


    def check_default_DT(self, idx: int):
        if self.DT_list[idx]:
            return self.DT_list[idx]
        else:
            today = TODAY
            if idx == 0:
                self.year = today.year
                return self.year
            elif idx == 1:
                self.month = today.month
                return self.month
            elif idx == 2:
                # 지금 주차가 몇주차인지 계산
                month_1st = dt.datetime(today.year, today.month, 1).weekday()
                one_week = dt.datetime(today.year, today.month, 1) - dt.timedelta(days=month_1st)
                today_week = (today - one_week).days // 7 + 1
                self.week = today_week
                return self.week
            elif idx == 3:
                self.day = today.day
                return self.day

summarization = Summarization()

# when2meet이 시작되면 화자별로 하나씩 생성되는 class
# 맨 처음 나오는 라벨을 기준으로 설정된다.
class When2meet():
    def __init__(self, name):
        self.name = name

        # 하위가 TRUE로 설정되면 상위 분류들은 모두 TRUE로 설정된다.
        # DT
        self.year = False
        self.month = False  # 가장 최신 값들을 setting한다.
        self.week = False
        self.day = False
        self.DT_list = [self.year, self.month, self.week, self.day]

        # TI
        self.hour = False
        self.minute = False

        # final_set
        self.datetimes = []
        self.no_datetimes = []  # 겹치는 일정이 없으나 minus가 발생한 값들을 저장하는 공간.
        self.TI_datetimes = []  # 처음 TI만 있는 경우를 말함(+)
        self.no_TI_datetimes = []

    def check_default_DT(self, idx: int):
        result = []
        for i, w in enumerate(self.DT_list[:idx]):
            if w:
                result.append(w)
                summarization.set_default_DT(i, w)
            else:
                tmp = summarization.check_default_DT(i)
                if i == 0:
                    self.year = tmp
                elif i == 1:
                    self.month = tmp
                elif i == 2:
                    self.week = tmp
                elif i == 3:
                    self.day = tmp

                result.append(tmp)
        return result

    # 더하기 전, 갖고있는 값들과 비교해 False거나, 현재 값이 더 크다면 값들을 setting 해준다.
    def set_default_DT(self):
        for one in self.datetimes:
            begin_DT, end_DT, begin_TI, end_TI = one

            if begin_DT.year:
                if not self.year:
                    self.year = begin_DT.year
                elif self.year < begin_DT.year:
                    self.year = begin_DT.year

            if begin_DT.month:
                if not self.month:
                    self.month = begin_DT.month
                elif self.month < begin_DT.month:
                    self.month = begin_DT.month

            if begin_DT.week:
                if not self.week:
                    self.week = begin_DT.week
                elif self.week < begin_DT.week:
                    self.week = begin_DT.week
            if begin_DT.flag_week:
                today = TODAY
                if not self.week:
                    if begin_DT.flag_week >= 100:
                        if begin_DT.flag_week == 100:
                            month_last = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(
                                days=1)).weekday()
                            last_week = dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(
                                days=month_last + 1)
                        else:  # 다음 주 구하는 식
                            count = begin_DT.flag_week - 101
                            count_day = today + dt.timedelta(weeks=count)
                            month_1st = dt.datetime(count_day.year, count_day.month, 1).weekday()
                            one_week = dt.datetime(count_day.year, count_day.month, 1) - dt.timedelta(days=month_1st)
                            count_week = (count_day - one_week).days // 7 + 1
                            self.week = count_week
                    else:
                        self.week = begin_DT.flag_week
                elif self.week < begin_DT.flag_week:
                    if begin_DT.flag_week >= 100:  # 101이 이번주 1
                        if begin_DT.flag_week == 100:
                            month_last = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(
                                days=1)).weekday()
                            last_week = dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(
                                days=month_last + 1)
                        else:  # 다음 주 구하는 식
                            count = begin_DT.flag_week - 101
                            count_day = today + dt.timedelta(weeks=count)
                            month_1st = dt.datetime(count_day.year, count_day.month, 1).weekday()
                            one_week = dt.datetime(count_day.year, count_day.month, 1) - dt.timedelta(days=month_1st)
                            count_week = (count_day - one_week).days // 7 + 1
                            self.week = count_week
                    else:
                        self.week = begin_DT.flag_week
            if begin_DT.day:
                if not self.day:
                    self.day = begin_DT.day

        self.DT_list = [self.year, self.month, self.week, self.day]
        #         print('<when2meet - set_default>')
        #         print(self.DT_list)

        for i, w in enumerate(self.DT_list):
            if w:
                summarization.set_default_DT(i, w)

    def set_item(self):
        pass

    def sub_TI(self, upper_one: tuple, other_one: tuple):
        # Input으로 시간만을 tuple로 받아서 output으로 시간이 존재한다면 list or 시간이 존재하지 않는다면 False
        u_begin_TI_, u_end_TI_ = upper_one
        begin_TI_, end_TI_ = other_one

        # 지정되어 있지 않은 값일 시 바꿔준다.
        if u_begin_TI_.hour == -1:
            u_begin_TI_.hour = 0
        if u_end_TI_.hour == -1:
            u_end_TI_.hour = 24
        if begin_TI_.hour == -1:
            begin_TI_.hour = 0
        if end_TI_.hour == -1:
            end_TI_.hour = 24

        # 0. 아예 겹치면 DT 삭제
        if begin_TI_ == u_begin_TI_ and end_TI_ == u_end_TI_:
            return False
        # upper과 겹치는 부분만큼을 확인한다.
        # 1.빼주는 것의 범위에 upper가 들어오는 경우 = 해당 TI가 텅비게 되므로 아예 DT자체를 빼준다.
        #   -> begin의 경우 other이 upper보다 작아야 함 & end의 경우 other이 upper보다 커야함
        elif begin_TI_ <= u_begin_TI_ and end_TI_ >= u_end_TI_:
            return False
        # 2. upper가 other을 다 포함하는 경우 = 두개의 TI가 발생할 수도 있음.
        elif begin_TI_ >= u_begin_TI_ and end_TI_ <= u_end_TI_:
            if u_begin_TI_ == begin_TI_:
                return [(end_TI_, u_end_TI_)]
            elif end_TI_ == u_end_TI_:
                return [(u_begin_TI_, begin_TI_)]
            else:
                return [(u_begin_TI_, begin_TI_), (end_TI_, u_end_TI_)]
        # 3. 뒤쪽만 나간 경우
        elif begin_TI_ > u_begin_TI_ and begin_TI_ < u_end_TI_ and u_end_TI_ < end_TI_:
            return [(u_begin_TI_, begin_TI_)]
        # 4. 앞쪽만 나간 경우
        elif end_TI_ < u_end_TI_ and end_TI_ > u_begin_TI_ and u_begin_TI_ > begin_TI_:
            return [(end_TI_, u_end_TI_)]
        # 5. 아예 겹치지 않는 경우 upper을 그대로 반환한다.
        else:
            return [upper_one]

    def __add__(self, other):  # 기간을 set하거나, 추가적으로 더하는 연산

        # 더하기 전, 갖고있는 값들과 비교해 False거나, 현재 값이 더 크다면 값들을 setting 해준다.

        # 1.현재와 비교해서, 일정이 없다면 단순 더한다.(add)
        # 2.현재와 비교해서, 일정이 있다면 앞의 일정을 없애고 더한다.(reset)
        # 2-1. 일정이 있고, DT만 설정되어 있을 때(DT에 집중)
        # 2-2. 일정이 있고, DT와 TI가 둘 다 나왔을 때(TI에 집중)
        # 2-2-*. TI다음의 보조사/격조사를 체크한다.
        # 2-2-1. 에,만,에만 -> DAY 단위 조건 재지정
        # 2-2-2. 에도, X -> 기존 TI에 더해 준다.

        level_count = []
        new_datetimes = []
        if self.datetimes:
            for one in other.refined_datetime:  # 하나의 스케쥴=한 문장에 등장한 datetime들
                # upper_one_dt = [(idx, upper_one), (idx, upper_one), ...]
                upper_one_dt = self.contain(one)
                if upper_one_dt:  # 포함되어 있는게 있다면
                    # 2.큰 리스트에 모아주고
                    level_count.append((upper_one_dt, one))
                else:  # 1.포함되어 있는게 없으면 단순 더해준다.
                    #############################self에서 안겹치는건 어떻게 더해줄것인가?
                    new_datetimes.append(one)

            # 일단 가장 상위 level로 ... 걍 포함되어 있는게 있다면 TI만 체크해서 new_datetimes에 넣는다.
            for upper, one in level_count:
                if len(upper) > 1:  # DT당 여러 개의 TI가 있을 때
                    # 2-2-*. TI다음의 보조사/격조사를 체크한다.
                    # 2-2-1. 에,만,에만 -> DAY 단위 조건 재지정
                    # 2-2-2. 에도, X -> 기존 TI에 더해 준다.

                    # 일단은 조건 재지정으로 짜자
                    new_datetimes.append(one)

                elif len(upper) == 1:  # DT당 하나의 TI만 있을 때
                    idx, (u_begin_DT, u_end_DT, u_begin_TI, u_end_TI) = upper[0]
                    begin_DT, end_DT, begin_TI, end_TI = one
                    upper_bound = u_begin_DT.return_flag_max()
                    one_bound = begin_DT.return_flag_max()

                    # 2-1.일정이 있고, DT만 설정되어 있을 때(DT에 집중) -> one의 TI의 hour이 0~24이거나 -1~-1, upper의 time을 그대로 받음
                    # [0]나 다음주 오후에 다돼! -> [1-1]아 일요일만 될 듯
                    if begin_TI.hour == -1 and end_TI.hour == -1:
                        new_datetimes.append((begin_DT, end_DT, u_begin_TI, u_end_TI))

                    ########################################################
                    # 2-2.일정이 있고, DT와 TI가 둘 다 나왔을 때(TI에 집중)
                    # [0]나 다음주 오전에는 다 돼! -> [1-2]아 일요일은 저녁에만 될 듯 [1-3]아 일요일은 저녁에도 돼
                    # 2-2-*. TI다음의 보조사/격조사를 체크한다.
                    # 2-2-1. 에,만,에만 -> DAY 단위 조건 재지정
                    # 2-2-2. 에도, X -> 기존 TI에 더해 준다.
                    else:
                        # 일단은 조건 재지정으로 짜자
                        new_datetimes.append(one)

                else:
                    print('error!')
                    print(len(upper))

            tmp = []
            for one in self.datetimes:  # 만약 self에 있는것들 중 new_datetimes에 없는게 있다면 더해준다.
                contain_date = []
                begin_DT, end_DT, begin_TI, end_TI = one
                for upper_one in new_datetimes:
                    u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = upper_one
                    if (
                            u_begin_DT.year == begin_DT.year and u_begin_DT.month == begin_DT.month and u_begin_DT.day == begin_DT.day) and (
                            u_end_DT.year == end_DT.year and u_end_DT.month == end_DT.month and u_end_DT.day == end_DT.day):
                        contain_date.append(upper_one)
                if contain_date:
                    pass
                else:
                    new_datetimes.append(one)

        else:
            for one in other.refined_datetime:
                new_datetimes.append(one)

        # 만약 new_datetimes에 1)TI만 있거나 2)TI만 있는 경우+datetime가 존재하는 경우를 처리한다.
        only_TI_datetimes = []
        tmp = []
        for one in new_datetimes:
            begin_DT, end_DT, begin_TI, end_TI = one
            if begin_DT.year == 0 and begin_DT.month == 0 and begin_DT.day == 0:
                # print('plus에서 TI만 있는경우 처리')
                only_TI_datetimes.append((begin_TI, end_TI))
            else:
                tmp.append(one)

        if only_TI_datetimes:
            if len(tmp) > 0:  # 2)TI만 있는 경우 + datetime가 존재하는 경우
                new_datetimes = tmp
                tmp = []
                for (set_begin_TI, set_end_TI) in only_TI_datetimes:
                    for one in new_datetimes:
                        begin_DT, end_DT, begin_TI, end_TI = one
                        # 지정 vs 재지정이 나누어져야 하지만, 지금은 무조건 재지정으로 설정. ###########################
                        tmp.append((begin_DT, end_DT, set_begin_TI, set_end_TI))

                new_datetimes = tmp
            else:  # 1)TI만 있는 경우 = DT는 상관없고, 이 시간대에만 된다.
                # 지금까지 나온 값 중 가장 큰 값의 시간만 설정해야 함.
                self.TI_datetimes += only_TI_datetimes
                new_datetimes = tmp

        #         print(new_datetimes)
        self.datetimes = new_datetimes
        self.set_default_DT()
        ###연산할 때 무조건 when2meet의 값들을 set하고, sum과 통신해야됨. (default값)

    def __sub__(self, other):  # 기간을 추가적으로 빼는 연산

        # 1.현재와 비교해서, 일정이 없는데 해당 값을 빼려고 한다면 self.no_datetimes에 넣어준다. (intersection에서 사용)
        # 2.현재와 비교해서, 일정이 있다면 기존 일정에서 단순 빼기한다.
        # 2-1. 일정이 있고, DT만 설정되어 있을 때(DT에 집중) : 해당 DAY 자체를 삭제
        # 2-2. 일정이 있고, DT와 TI가 둘 다 나왔을 때(TI에 집중) : DT는 냅두고, TI를 뺀 값을 넣는다.

        level_count = []
        only_no_TI_datetimes = []
        if self.datetimes:
            for one in other.refined_datetime:  # 하나의 스케쥴=한 문장에 등장한 datetime들
                begin_DT, end_DT, begin_TI, end_TI = one
                # upper_one_dt = [(idx, upper_one), (idx, upper_one), ...]
                upper_one_dt = self.contain(one)
                if upper_one_dt:  # 포함되어 있는게 있다면
                    # 2.큰 리스트에 모아주고
                    level_count.append((upper_one_dt, one))
                else:  # 1.포함되어 있는게 없으면 단순 list에 추가해준다. (TI만 있을 시 따로 연산)
                    if begin_DT.year == 0 and begin_DT.month == 0 and begin_DT.day == 0:
                        only_no_TI_datetimes.append((begin_TI, end_TI))
                    else:
                        self.no_datetimes.append(one)

            # 일단 가장 상위 level로 ... 걍 포함되어 있는게 있다면 TI만 체크해서 self.datetimes에 넣는다.
            for upper, one in level_count:
                if len(upper) > 1:  # DT당 여러 개의 TI가 있을 때
                    idx, (u_begin_DT, u_end_DT, u_begin_TI, u_end_TI) = upper[0]
                    # 2-1.일정이 있고, DT만 설정되어 있을 때(DT에 집중)
                    # self.datetimes에서 해당 DT인 값들을 삭제
                    if begin_TI.hour == -1 and end_TI.hour == -1:
                        rm_tmp = []
                        for tmp_one in self.datetimes:
                            if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT:
                                pass
                            else:
                                rm_tmp.append(tmp_one)
                        self.datetimes = rm_tmp

                    else:  # 2-2.
                        for tmp_upper in upper:
                            idx, (u_begin_DT, u_end_DT, u_begin_TI, u_end_TI) = tmp_upper
                            begin_DT, end_DT, begin_TI, end_TI = one

                            tmp_TI = self.sub_TI((u_begin_TI, u_end_TI), (begin_TI, end_TI))
                            rm_tmp = []
                            for tmp_one in self.datetimes:
                                if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT:
                                    pass
                                else:
                                    rm_tmp.append(tmp_one)
                            self.datetimes = rm_tmp

                            if tmp_TI:
                                for (b_tmp, e_tmp) in tmp_TI:
                                    self.datetimes.append((u_begin_DT, u_end_DT, b_tmp, e_tmp))

                elif len(upper) == 1:  # DT당 하나의 TI만 있을 때
                    idx, (u_begin_DT, u_end_DT, u_begin_TI, u_end_TI) = upper[0]
                    begin_DT, end_DT, begin_TI, end_TI = one
                    upper_bound = u_begin_DT.return_flag_max()
                    one_bound = begin_DT.return_flag_max()

                    # 2-1.일정이 있고, DT만 설정되어 있을 때(DT에 집중)
                    # self.datetimes에서 해당 DT인 값을 삭제
                    if (begin_TI.hour == -1 and end_TI.hour == -1) or (begin_TI.hour == 0 and end_TI.hour == 24):
                        rm_tmp = []
                        for tmp_one in self.datetimes:
                            if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT:
                                pass
                            else:
                                rm_tmp.append(tmp_one)
                        self.datetimes = rm_tmp

                    # 2-2.일정이 있고, DT와 TI가 둘 다 나왔을 때(TI에 집중)
                    # self.datetimes에서 해당 DT인 값의 TI를 재지정해준다.
                    else:
                        tmp_TI = self.sub_TI((u_begin_TI, u_end_TI), (begin_TI, end_TI))
                        rm_tmp = []
                        for tmp_one in self.datetimes:
                            if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT:
                                pass
                            else:
                                rm_tmp.append(tmp_one)
                        self.datetimes = rm_tmp

                        if tmp_TI:
                            # [(begin_TI, end_TI)] 꼴들이 반환됨
                            # 원래 값은 삭제한 뒤
                            # 해당 DT의 값을 바꿔서 넣어줌
                            for (b_tmp, e_tmp) in tmp_TI:
                                self.datetimes.append((u_begin_DT, u_end_DT, b_tmp, e_tmp))

                else:
                    print('error!')
                    print(len(upper))
        else:
            for one in other.refined_datetime:
                begin_DT, end_DT, begin_TI, end_TI = one
                if begin_DT.year == 0 and begin_DT.month == 0 and begin_DT.day == 0:
                    only_no_TI_datetimes.append((begin_TI, end_TI))
                else:
                    self.no_datetimes.append(one)

        # 만약 self.datetimes에 1)TI만 있거나 2)TI만 있는 경우+datetime가 존재하는 경우를 처리한다.
        if only_no_TI_datetimes:
            if len(self.datetimes) > 0:  # 2)TI만 있는 경우 + datetime가 존재하는 경우
                tmp = []
                for begin_TI, end_TI in only_no_TI_datetimes:
                    for tmp_upper in self.datetimes:
                        u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = tmp_upper
                        tmp_TI = self.sub_TI((u_begin_TI, u_end_TI), (begin_TI, end_TI))
                        # 지정 vs 재지정이 나누어져야 하지만, 지금은 무조건 재지정으로 설정. ###########################
                        if tmp_TI:
                            for one_TI in tmp_TI:
                                tmp.append((u_begin_DT, u_end_DT, one_TI[0], one_TI[1]))
                self.datetimes = tmp
            else:  # 1)TI만 있는 경우 = DT는 상관없고, 이 시간대에만 된다.
                # 지금까지 나온 값 중 가장 큰 값의 시간만 설정해야 함.
                # 빈 값에다가 빼기 위한 연산이다.
                self.no_TI_datetimes += only_no_TI_datetimes

    def contain(self, one_datetime):  # 각각 비교해서 겹치는 DT가 있을 시 겹치는 기간 return
        # DATE-DAY 기준으로 한다.
        # self.datetimes = []
        contain_date = []
        begin_DT, end_DT, begin_TI, end_TI = one_datetime
        for idx, upper_one in enumerate(self.datetimes):
            u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = upper_one
            if (
                    u_begin_DT.year == begin_DT.year and u_begin_DT.month == begin_DT.month and u_begin_DT.day == begin_DT.day) and (
                    u_end_DT.year == end_DT.year and u_end_DT.month == end_DT.month and u_end_DT.day == end_DT.day):
                contain_date.append((idx, upper_one))
        #         print('test',contain_date)

        return contain_date

    def contain_DT(self, compare_list, one_datetime):
        contain_date = []
        begin_DT, end_DT, begin_TI, end_TI = one_datetime
        for upper_one in compare_list:
            u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = upper_one
            if (
                    u_begin_DT.year == begin_DT.year and u_begin_DT.month == begin_DT.month and u_begin_DT.day == begin_DT.day) and (
                    u_end_DT.year == end_DT.year and u_end_DT.month == end_DT.month and u_end_DT.day == end_DT.day):
                contain_date.append(upper_one)
        return contain_date

    def contain_TI(self, one, other):
        one_begin, one_end = one
        other_begin, other_end = other
        # 두개의 TI가 겹치는 범위를 반환한다.
        # 안겹치면 False
        if one_end <= other_begin or other_end <= one_begin:
            return False
        else:
            # begin은 더 큰 값을, end는 더 작은 값을 반환한다.
            tmp = []
            if one_begin >= other_begin:
                tmp.append(one_begin)
            else:
                tmp.append(other_begin)
            if one_end <= other_end:
                tmp.append(one_end)
            else:
                tmp.append(other_end)

            return (tmp[0], tmp[1])

    def final_set(self):
        # TI_datetimes에 있는 것과 no_TI_datetimes에 있는 것들을 연산한다.
        tmp = []
        for (begin_TI, end_TI) in self.TI_datetimes:
            # 일단 재지정으로 짠다. (사실 다른 TI가 나오면 추가 지정일 것이다.)
            for upper_one in self.datetimes:
                u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = upper_one
                tmp.append((u_begin_DT, u_end_DT, begin_TI, end_TI))
        if tmp:
            self.datetimes = tmp

        tmp = []
        for (begin_TI, end_TI) in self.no_TI_datetimes:
            # 일단 재지정으로 짠다. (사실 다른 TI가 나오면 추가 지정일 것이다.)
            for upper_one in self.datetimes:
                u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = upper_one
                # 잔나비
                tmp_TI = self.sub_TI((u_begin_TI, u_end_TI), (begin_TI, end_TI))
                # 지정 vs 재지정이 나누어져야 하지만, 지금은 무조건 재지정으로 설정. ###########################
                if tmp_TI:
                    for one_TI in tmp_TI:
                        tmp.append((u_begin_DT, u_end_DT, one_TI[0], one_TI[1]))
        if tmp:
            self.datetimes = tmp

    def __repr__(self):
        return f'When2meet(name:{self.name}, datetimes:{self.datetimes})'  # , {self.DT_list}

    def intersection(self, other):  # 교집합 구하는 연산
        intersect_datetimes = []

        # 0.만약 겹치는게 하나도 없다면 None을 return해 구분해 준다.
        # 모두 가능한게 비어있는 리스트이므로, 이를 파악할 flag를 설정해준다.
        self_flag = self.datetimes
        other_flag = other.datetimes

        if self.datetimes == None or other.datetimes == None:
            tmp = When2meet('All')
            tmp.datetimes = None
            return tmp

        # 1.other.datetimes들과 DT가 겹치는 것들만 반환한다.

        # 만약 datetimes가 비어있다면 예전 거 그대로 갖고오게 하기
        if not self.datetimes and other.datetimes:
            other.final_set()
            self.datetimes = other.datetimes
            # 만약 TI만 설정되어 있는 값이 있다면 ex.오후면 상관없어~/오후만 아니면 돼
            self.final_set()
            intersect_datetimes = self.datetimes

        elif not other.datetimes and self.datetimes:
            self.final_set()
            other.datetimes = self.datetimes
            # 만약 TI만 설정되어 있는 값이 있다면 ex.오후면 상관없어~/오후만 아니면 돼
            other.final_set()
            intersect_datetimes = other.datetimes
            # print(intersect_datetimes)

        elif not self.datetimes and not other.datetimes:  # 둘 다 비어있다면
            pass

        else:
            # datetimes가 비어있지 않지만, 시간만 set되어 있는 경우도 넣어놔야 됨!! ex) 오후면 다 돼! -> 넣음
            # 0.TI_datetimes에 있는 것과 no_TI_datetimes에 있는 것들을 연산한다.
            self.final_set()
            other.final_set()

            # 1. 있는 것들 중 DT가 겹치는 것들만 list에 추가한다.
            for other_one in other.datetimes:
                other_begin_DT, other_end_DT, other_begin_TI, other_end_TI = other_one

                same_dt_self = self.contain(other_one)
                same_dt_self = [x[1] for x in same_dt_self]
                # same dt는 두개 이상일 수도 있음
                # 2. 있는 것들 중 TI가 겹치는 것들만 list에 추가한다.
                for dt_self in same_dt_self:
                    self_begin_DT, self_end_DT, self_begin_TI, self_end_TI = dt_self

                    how_TI = self.contain_TI((self_begin_TI, self_end_TI), (other_begin_TI, other_end_TI))
                    if how_TI:
                        intersect_datetimes.append((self_begin_DT, self_end_DT, how_TI[0], how_TI[1]))
                    # how_TI가 없는건 겹치지 않는 다는 것. = 추가하지 X

            if not intersect_datetimes:
                tmp = When2meet('All')
                tmp.datetimes = None
                return tmp

        # 3.그 겹치는 것들 중 self.no_datetimes 나 other.no_datetime에 있는게 있다면 빼준다.
        all_no_datetimes = self.no_datetimes + other.no_datetimes
        former = intersect_datetimes

        for one in all_no_datetimes:
            # intersection_datetimes와 같은 게 있다면,
            begin_DT, end_DT, begin_TI, end_TI = one
            u_list = self.contain_DT(intersect_datetimes, one)
            if (u_list):
                for one_up in u_list:
                    u_begin_DT, u_end_DT, u_begin_TI, u_end_TI = one_up

                    # 같은게 있으나, DT에만 집중 됐을 때 -> 삭제
                    if (begin_TI.hour == -1 and end_TI.hour == -1) or (begin_TI.hour == 0 and end_TI.hour == 24):
                        rm_tmp = []
                        for tmp_one in intersect_datetimes:
                            if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT:
                                pass
                            else:
                                rm_tmp.append(tmp_one)
                        intersect_datetimes = rm_tmp

                    # 2-2.일정이 있고, DT와 TI가 둘 다 나왔을 때(TI에 집중)
                    else:
                        tmp_TI = self.sub_TI((u_begin_TI, u_end_TI), (begin_TI, end_TI))
                        rm_tmp = []
                        for tmp_one in intersect_datetimes:
                            if tmp_one[0] == u_begin_DT and tmp_one[1] == u_end_DT and tmp_one[2] == u_begin_TI and \
                                    tmp_one[3] == u_end_TI:
                                pass
                            else:
                                rm_tmp.append(tmp_one)
                        intersect_datetimes = rm_tmp

                        if tmp_TI:
                            for (b_tmp, e_tmp) in tmp_TI:
                                intersect_datetimes.append((u_begin_DT, u_end_DT, b_tmp, e_tmp))

        tmp = When2meet('All')

        # 만약 intersect는 비어있는데 former가 비어있지 않다면 = 계산 후 겹치는게 하나도 없었다면
        if not intersect_datetimes and former:
            tmp.datetimes = None
            return tmp

        # 만약 intersect_datetimes에 아무것도 없지만, self/other.datetimes 가 둘다 있다면 겹치는 날이 없는 것.
        if not intersect_datetimes and self_flag and other_flag:
            tmp.datetimes = None
            return tmp
        else:
            tmp.datetimes = intersect_datetimes
            tmp.no_datetimes = all_no_datetimes
            tmp.TI_datetimes = self.TI_datetimes + other.TI_datetimes
            tmp.no_TI_datetimes = self.no_TI_datetimes + other.no_TI_datetimes
            return tmp

class Mydate():
    def __init__(self, year=0, month=0, week=0, day=0, weekday=-1, before=0, after=0):
        self.year = year
        self.month = month
        self.week = week
        self.day = day
        self.weekday = weekday
        self.before = before
        self.after = after
        self.all_list = [self.year, self.month, self.week, self.day, self.weekday, self.before, self.after]

        # 여기를 고쳐야 함!!!!!!!!!!생성될 때 같이 set하게끔 해버리자
        self.flag_year = year
        self.flag_month = month
        self.flag_week = week
        self.flag_day = day
        self.flag_weekday = weekday
        self.all_flag_list = [self.flag_year, self.flag_month, self.flag_week, self.flag_day, self.flag_weekday]

    #         self.flag_before = before
    #         self.flag_after = after

    def __repr__(self):
        weekday_list = ['월', '화', '수', '목', '금', '토', '일']
        if self.weekday >= 0:
            tmp = f'Mydate({self.year}년 {self.month}월 {self.week}주 {self.day}일 {weekday_list[self.weekday]}요일, before:{self.before} after:{self.after})'
        else:
            tmp = f'Mydate({self.year}년 {self.month}월 {self.week}주 {self.day}일, before:{self.before} after:{self.after})'
        return tmp

    def print_beforeNafter(self):
        print(f'before: {self.before} after: {self.after}')

    def print_flags(self):
        print(
            f'flag - year:{self.flag_year}, month:{self.flag_month}, week:{self.flag_week}, day:{self.flag_day}, wday:{self.flag_weekday}')

    def set_flag(self, year=0, month=0, week=0, day=0, weekday=-1):
        self.flag_year = year
        self.flag_month = month
        self.flag_week = week
        self.flag_day = day
        self.flag_weekday = weekday
        self.all_flag_list = [self.flag_year, self.flag_month, self.flag_week, self.flag_day, self.flag_weekday]

    def return_max(self):
        if self.weekday != -1:
            return 4
        elif self.day:
            return 3
        elif self.week:
            return 2
        elif self.month:
            return 1
        elif self.year:
            return 0

    def return_min(self):
        if self.year:  # year이 설정되어(=다 되어) 있을 때
            return 0
        elif self.month:  # month
            return 1
        elif self.week:
            return 2
        elif self.day:
            return 3
        elif self.weekday != -1:
            return 4
        else:  # 다 설정되어 있지 않을 때
            return 5

    def return_flag_max(self):
        if self.flag_weekday != -1:
            return 4
        elif self.flag_day:
            return 3
        elif self.flag_week:
            return 2
        elif self.flag_month:
            return 1
        elif self.flag_year:
            return 0

    def __add__(self, other):
        result = []
        for idx, (s, o) in enumerate(zip(self.all_list, other.all_list)):
            if idx != 4 and o == 0:
                result.append(s)
            elif idx == 4 and o == -1:
                result.append(s)
            else:
                result.append(o)

        result_Mydate = Mydate(result[0], result[1], result[2], result[3], result[4], result[5], result[6])

        result_flag = []
        for idx, (s, o) in enumerate(zip(self.all_flag_list, other.all_flag_list)):
            if idx != 4 and o == 0:
                result_flag.append(s)
            elif idx == 4 and o == -1:
                result_flag.append(s)
            else:
                result_flag.append(o)

        result_Mydate.set_flag(*result_flag)

        return result_Mydate

    def __eq__(self, other):
        if self.year == other.year and self.month == other.month and self.day == other.day:
            return True
        else:
            return False

class Mytime():
    def __init__(self, hour=-1, minute=0, pm=False):
        self.hour = hour
        self.minute = minute
        self.all_list = [self.hour, self.minute]

        self.pm = pm
        self.flag_hour = False
        if hour != -1:
            self.flag_hour = hour

    def __repr__(self):
        return f'Mytime({self.hour}시 {self.minute}분)'

    def __add__(self, other):
        result = []

        if self.pm == True and other.pm == False and other.hour < 12:
            # 그리고 12시를 넘지 않는다면 +12를 더해준다.
            # -> 나중에 범위 + point꼴로 바꿔야 할것 같은데
            # 일단 이렇게만 바꿔놓자.
            if other.hour == -1:
                result.append(self.all_list[0])
            else:
                result.append(other.all_list[0] + 12)
            result.append(other.all_list[1])

        else:
            for s, o in zip(self.all_list, other.all_list):
                if o == 0 or o == -1:
                    result.append(s)
                else:
                    result.append(o)
        return Mytime(result[0], result[1])

    def __lt__(self, other):
        # 6:00 vs 6:30
        return self.hour * 100 + self.minute < other.hour * 100 + other.minute

    def __le__(self, other):
        return self.hour * 100 + self.minute <= other.hour * 100 + other.minute

    def __gt__(self, other):
        return self.hour * 100 + self.minute > other.hour * 100 + other.minute

    def __ge__(self, other):
        return self.hour * 100 + self.minute >= other.hour * 100 + other.minute

    def __eq__(self, other):
        return self.hour * 100 + self.minute == other.hour * 100 + other.minute

    def __ne__(self, other):
        return self.hour * 100 + self.minute != other.hour * 100 + other.minute

    def return_min(self):
        if self.hour:
            return 0
        elif self.minute:
            return 1
        else:
            return 2

class Myadv():
    def __init__(self, adv, index):
        self.adv = adv
        self.index = index
    def __repr__(self):
        return f'Myadv(adv: {self.adv}, index: {self.index})'

persons = [When2meet(x) for x in range(20)]
speakers = {name:person for name,person in zip(range(20), persons)}

# 문장 하나로 부터 얻는 SCEHDULE
class Schedule():
    def __init__(self, ner_list, intent, name):
        self.name = name
        self.operator = intent
        # DT
        self.year = False
        self.month = False
        self.week = False
        self.day = False
        # TI
        self.hour = False
        self.uncertain_hour = False
        self.minute = False

        self.sch_list = []
        self.split_time = []
        self.sep_datetime = []
        self.raw_datetime = []

        self.refined_datetime = []

        self.now = TODAY

        tagged_label_list = []

        # ner_list가 없다면 동조하는 걸로 판단.

        # ner list 정제해주어야 함
        # 1.시점인지 기간인지 파악
        # 2.숫자가 하나라도 들어갔는지 안들어갔는지 파악
        # 3.상대적인지 절대적인지 파악
        if ner_list:  # ('다음 주','DT_WEEK'), ('수','DT_DAY'), ('목','DT_DAY'),('저녁동안','TI_DURATION')
            for text, label in ner_list:
                dt_or_ti = label[:2]
                if dt_or_ti == 'DT':
                    results = classify_point((text, label))
                    results = classify_abs(results)
                    tagged_label_list.append(results)
                else:
                    results = classify_point_TI((text, label))
                    results = classify_TI(results)
                    tagged_label_list.append(results)

        # 'parsing': [('저', None)] 이라면, 없애준다.
        tagged_label_list = [x for x in tagged_label_list if
                             not (len(x['parsing']) == 1 and x['parsing'][0][1] == None)]


        # 단어 하나에 대해 set -> 단순 datetime 객체를 추가하는 식으로 할거임.
        # parsing list에 대해

        final_parsing_list = []
        if tagged_label_list:
            for one in tagged_label_list:

                one_datetime = []
                ner, durNpoint, parsing = one['ner'], one['durNpoint'], one['parsing']
                if ner[:2] == 'DT':
                    for segment in parsing:
                        if segment[1] == True and len(segment) > 3:
                            seg_text = segment[0]
                            seg_ner = segment[2]
                            seg_rel_or_abs = segment[3]
                            seg_label = segment[4]

                            if seg_ner == 'DT_YEAR':
                                self.year = True
                                if seg_rel_or_abs == 'REL':
                                    if seg_label == 0:  # 내년
                                        one_datetime.append(Mydate(self.now.year + 1))
                                    elif seg_label == 1:  # 올해
                                        one_datetime.append(Mydate(self.now.year))
                                else:  # 'ABS'
                                    if seg_label == 0:
                                        tmp = int(seg_text[:4])
                                        one_datetime.append(Mydate(tmp))


                            elif seg_ner == 'DT_MONTH':
                                self.month = True
                                if seg_rel_or_abs == 'REL':  # 그달
                                    if seg_label == 0:
                                        pass
                                    elif seg_label == 1:  # 다*담달
                                        # '다'의 갯수를 구함
                                        p = re.compile('담|다음')
                                        count = p.search(seg_text).start() + 1
                                        m = self.now.month + count
                                        one_datetime.append(Mydate(month=m))  ############ DURATION으로 바꿔줘야 할듯
                                    elif seg_label == 2:  # 이번달
                                        one_datetime.append(Mydate(month=self.now.month))
                                    # 나머지는 부사랑 오므로 무조건 DUR으로 tag될 것. 사실 QT로 태그되어야 한다.
                                    # 아웃풋을 timedelta로 해야될 것 같음...
                                    #################################################

                                else:  # 'ABS'
                                    if seg_label == 0:  # 막달
                                        one_datetime.append(Mydate(month=12))
                                    elif seg_label == 1:  # NN월
                                        if len(seg_text) == 2:
                                            one_datetime.append(Mydate(month=int(seg_text[0])))
                                        else:
                                            if seg_text[0] == 0:
                                                one_datetime.append(Mydate(month=int(seg_text[1])))
                                            else:
                                                one_datetime.append(Mydate(month=int(seg_text[:2])))
                                    elif seg_label == 2:  # '한글' 월
                                        one_datetime.append(Mydate(month=ordinal_number(seg_text[:-1])))

                            elif seg_ner == 'DT_WEEK':
                                self.week = True
                                weekday_list = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
                                today = self.now
                                weekday = today.weekday()

                                if seg_rel_or_abs == 'REL':
                                    if seg_label == 0:  # 다*담주
                                        self.year = True
                                        self.month = True

                                        p = re.compile('담|다음')
                                        count = p.search(seg_text).start() + 1
                                        begin, end = count * 7 - weekday, count * 7 + (7 - weekday) - 1
                                        begin_delta = dt.timedelta(days=begin)
                                        end_delta = dt.timedelta(days=end)

                                        b, e = today + begin_delta, today + end_delta

                                        tmp_b, tmp_e = Mydate(b.year, b.month, 0, b.day), Mydate(e.year, e.month, 0,
                                                                                                 e.day)
                                        tmp_b.set_flag(week=101 + count)
                                        tmp_e.set_flag(week=101 + count)

                                        one_datetime.append((tmp_b, tmp_e))

                                    elif seg_label == 1:  # 이번주
                                        end = 7 - weekday - 1
                                        end_delta = dt.timedelta(days=end)
                                        e = today + end_delta

                                        tmp_b, tmp_e = Mydate(today.year, today.month, 0, today.day), Mydate(e.year,
                                                                                                             e.month, 0,
                                                                                                             e.day)
                                        tmp_b.set_flag(week=101)
                                        tmp_e.set_flag(week=101)

                                        one_datetime.append((tmp_b, tmp_e))

                                    # 나머지는 부사랑 오므로 무조건 DUR으로 tag될 것.(실제로는 QT로 들어가야됨.)
                                    # 무조건 dt_duration으로 들어가므로 현재를 기준으로 봐야함.
                                    elif seg_label == 2:  # NN주
                                        if len(seg_text) == 2:
                                            end_delta = dt.timedelta(weeks=int(seg_text[0]))
                                            e = today + end_delta

                                            tmp_b, tmp_e = Mydate(e.year, e.month, 0, e.day), Mydate(e.year, e.month, 0,
                                                                                                     e.day)
                                            tmp_b.set_flag(week=101 + int(seg_text[0]))
                                            tmp_e.set_flag(week=101 + int(seg_text[0]))

                                            one_datetime.append((tmp_b, tmp_e))

                                        else:
                                            end_delta = dt.timedelta(weeks=int(seg_text[:-1].strip()))
                                            e = today + end_delta
                                            tmp_b, tmp_e = Mydate(e.year, e.month, 0, e.day), Mydate(e.year, e.month, 0,
                                                                                                     e.day)
                                            tmp_b.set_flag(week=101 + int(seg_text[:-1].strip()))
                                            tmp_e.set_flag(week=101 + int(seg_text[:-1].strip()))

                                            one_datetime.append((tmp_b, tmp_e))

                                    elif seg_label == 3:  # [일이삼사오]주일
                                        end_delta = dt.timedelta(weeks=ordinal_number(seg_text[0]))
                                        e = today + end_delta
                                        tmp_b, tmp_e = Mydate(e.year, e.month, 0, e.day), Mydate(e.year, e.month, 0,
                                                                                                 e.day)
                                        tmp_b.set_flag(week=101 + ordinal_number(seg_text[0]))
                                        tmp_e.set_flag(week=101 + ordinal_number(seg_text[0]))

                                        one_datetime.append((tmp_b, tmp_e))

                                    elif seg_label == 4:  # 한주
                                        end = 7 - weekday - 1
                                        end_delta = dt.timedelta(days=end)
                                        e = today + end_delta
                                        tmp_b, tmp_e = Mydate(e.year, e.month, 0, e.day), Mydate(e.year, e.month, 0,
                                                                                                 e.day)
                                        tmp_b.set_flag(week=102)
                                        tmp_e.set_flag(week=102)

                                        one_datetime.append((tmp_b, tmp_e))

                                else:  # 'ABS'
                                    if seg_label == 0:  # 첫 주
                                        one_datetime.append(Mydate(week=1))
                                    elif seg_label == 1:  # 마지막 주
                                        one_datetime.append(Mydate(week=100))
                                    elif seg_label == 2:  # 둘째 주
                                        one_datetime.append(Mydate(week=ordinal_number2(seg_text)))
                                    elif seg_label == 3:  # n째주
                                        one_datetime.append(Mydate(week=int(seg_text[0])))
                                    elif seg_label == 4:  # 두번째주
                                        one_datetime.append(Mydate(week=ordinal_number2(seg_text)))

                            elif seg_ner == 'DT_DAY':
                                self.day = True
                                today = self.now
                                if seg_rel_or_abs == 'REL':
                                    if seg_label == 0:  # 낼
                                        self.year = True
                                        self.month = True
                                        t = today + dt.timedelta(days=1)
                                        tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                        tmp_dt.set_flag(day=102)

                                        one_datetime.append(tmp_dt)

                                    elif seg_label == 1:
                                        self.year = True
                                        self.month = True
                                        if seg_text == '하루':
                                            t = today + dt.timedelta(days=1)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=102)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '이틀' or seg_label == '2틀' or seg_label == '모레':
                                            t = today + dt.timedelta(days=2)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=103)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '사흘' or seg_label == '글피':
                                            t = today + dt.timedelta(days=3)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=104)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '나흘':
                                            t = today + dt.timedelta(days=4)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=105)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '닷새':
                                            t = today + dt.timedelta(days=5)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=106)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '엿새':
                                            t = today + dt.timedelta(days=6)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=107)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '이레':
                                            t = today + dt.timedelta(days=7)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=108)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '여드레':
                                            t = today + dt.timedelta(days=8)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=109)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '아흐레':
                                            t = today + dt.timedelta(days=9)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=110)
                                            one_datetime.append(tmp_dt)
                                        elif seg_label == '열흘':
                                            t = today + dt.timedelta(days=10)
                                            tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                            tmp_dt.set_flag(day=111)
                                            one_datetime.append(tmp_dt)

                                    elif seg_label == 2:  # 오늘
                                        self.year = True
                                        self.month = True
                                        tmp_dt = Mydate(year=today.year, month=today.month, day=today.day)
                                        tmp_dt.set_flag(day=101)
                                        one_datetime.append(tmp_dt)

                                    elif seg_label == 3:  # 다음 날
                                        self.year = True
                                        self.month = True
                                        t = today + dt.timedelta(days=1)
                                        tmp_dt = Mydate(year=t.year, month=t.month, day=t.day)
                                        tmp_dt.set_flag(day=102)
                                        one_datetime.append(tmp_dt)

                                    elif seg_label == 4:  # 둘쨋날
                                        one_datetime.append(Mydate(day=ordinal_number2(seg_text)))

                                    elif seg_label == 5:  # 두번째날
                                        one_datetime.append(Mydate(day=ordinal_number2(seg_text)))

                                    elif seg_label == 6:  # 월요일
                                        w = 6  # 일요일
                                        for idx, i in enumerate('월화수목금토'):
                                            if i in seg_text:
                                                w = idx
                                        one_datetime.append(Mydate(weekday=w))

                                    elif seg_label == 7:  # 월
                                        w = 6  # 일요일
                                        for idx, i in enumerate('월화수목금토'):
                                            if i in seg_text:
                                                w = idx
                                        one_datetime.append(Mydate(weekday=w))

                                else:  # 'ABS'
                                    if seg_label == 0:  # NN일 # QT와 주의해야함. (3일 후)
                                        end = seg_text.find('일')
                                        one_datetime.append(Mydate(day=int(seg_text[:end])))

                                    elif seg_label == 1:  # 이십일
                                        one_datetime.append(Mydate(day=ordinal_number(seg_text[:-1])))

                                    elif seg_label == 2:  # NN
                                        one_datetime.append(Mydate(day=int(seg_text)))


                            elif seg_ner == 'DT_DURATION':
                                self.day = True
                                if seg_rel_or_abs == 'REL':
                                    if seg_label == 0:  # 평일
                                        one_datetime.append((Mydate(weekday=0), Mydate(weekday=4)))
                                    elif seg_label == 1:  # 주말
                                        one_datetime.append((Mydate(weekday=5), Mydate(weekday=6)))

                            elif seg_ner == 'DT_OTHERS':
                                if seg_rel_or_abs == 'ABS':
                                    if seg_label == 0:  # 2022/2/14  02/14
                                        if len(seg_text) <= 5:
                                            self.month = True
                                            self.day = True
                                            tmp = seg_text.split('/')
                                            tmp = [int(x) for x in tmp]
                                            one_datetime.append(Mydate(month=tmp[0], day=tmp[1]))
                                        else:
                                            self.year = True
                                            self.month = True
                                            self.day = True
                                            tmp = seg_text.split('/')
                                            tmp = [int(x) for x in tmp]
                                            one_datetime.append(Mydate(year=tmp[0], month=tmp[1], day=tmp[2]))

                                    elif seg_label == 1:  # 2022-02-4
                                        self.year = True
                                        self.month = True
                                        self.day = True
                                        tmp = seg_text.split('/')
                                        tmp = [int(x) for x in tmp]
                                        one_datetime.append(Mydate(year=tmp[0], month=tmp[1], day=tmp[2]))

                                    elif seg_label == 2:  # 2012.12.12    12.12
                                        if len(seg_text) <= 5:
                                            self.month = True
                                            self.day = True
                                            tmp = seg_text.split('.')
                                            tmp = [int(x) for x in tmp]
                                            one_datetime.append(Mydate(month=tmp[0], day=tmp[1]))
                                        else:
                                            self.year = True
                                            self.month = True
                                            self.day = True
                                            tmp = seg_text.split('.')
                                            tmp = [int(x) for x in tmp]
                                            one_datetime.append(Mydate(year=tmp[0], month=tmp[1], day=tmp[2]))

                                    elif seg_label == 3:  # 220401
                                        self.year = True
                                        self.month = True
                                        self.day = True
                                        one_datetime.append(Mydate(year=int(seg_text[:2]), month=int(seg_text[2:4]),
                                                                   day=int(seg_text[4:])))

                                    elif seg_label == 4:  # 0401, 2020
                                        if int(seg_text) > 999:
                                            self.month = True
                                            self.day = True
                                            one_datetime.append(Mydate(month=int(seg_text[:2]), day=int(seg_text[2:4])))
                                        else:
                                            self.year = True
                                            one_datetime.append(Mydate(year=int(seg_text[:2])))

                        # 기간 부사라면
                        elif segment[1] == False and len(segment) >= 3:
                            text = segment[0]
                            adv = segment[2]
                            one_datetime.append(Myadv(text, adv))

                        # 신경쓰지 x
                        else:
                            pass

                else:  # TI
                    for segment in parsing:
                        # NER이라면
                        if segment[1] == True:
                            seg_text = segment[0]
                            seg_ner = segment[2]
                            seg_label = segment[3]
                            if seg_ner == 'TI_DURATION':

                                if seg_label == 0:  # 오전|오후|AM|PM|am|pm
                                    self.hour = True
                                    if seg_text == '오전' or seg_text == 'AM' or seg_text == 'am':
                                        one_datetime.append((Mytime(hour=0), Mytime(hour=12)))

                                    elif seg_text == '오후' or seg_text == 'PM' or seg_text == 'pm':
                                        one_datetime.append((Mytime(hour=12, pm=True), Mytime(hour=24, pm=True)))

                                elif seg_label == 1:  # 아침|점심|저녁|새벽|낮|밤
                                    self.hour = True
                                    if seg_text == '아침':
                                        one_datetime.append((Mytime(hour=6), Mytime(hour=12)))
                                    elif seg_text == '점심':
                                        one_datetime.append((Mytime(hour=11), Mytime(hour=14)))
                                    elif seg_text == '저녁':
                                        one_datetime.append((Mytime(hour=17, pm=True), Mytime(hour=21, pm=True)))
                                    elif seg_text == '새벽':
                                        one_datetime.append((Mytime(hour=0), Mytime(hour=6)))
                                    elif seg_text == '낮':
                                        one_datetime.append((Mytime(hour=12), Mytime(hour=18)))
                                    elif seg_text == '밤':
                                        one_datetime.append((Mytime(hour=18, pm=True), Mytime(hour=0, pm=True)))

                            elif seg_ner == 'TI_HOUR':
                                self.hour == True
                                if seg_label == 0:  # 정오, 자정
                                    if seg_text == '정오':
                                        one_datetime.append(Mytime(hour=12))
                                    elif seg_text == '자정':
                                        one_datetime.append(Mytime(hour=0))

                                elif seg_label == 1:  # nn시간
                                    if len(seg_text) == 4:
                                        tmp = int(seg_text[:2])
                                    else:
                                        tmp = int(seg_text[0])
                                    one_datetime.append(dt.timedelta(hours=tmp))

                                elif seg_label == 2:  # nn시
                                    tmp = int(seg_text[:-1])
                                    self.uncertain_hour = True  # 8시라고 했을 때 아침 8시인지 아닌지 명확하지 않음..
                                    one_datetime.append(Mytime(hour=tmp))
                                    # 만약에 한다면 13시 이상은 그대로,
                                    # 오후: 1~12시 까지는 보통 오후로 tag해야됨.

                                elif seg_label == 3:  # 두시간
                                    one_datetime.append(dt.timedelta(hours=cardinal_number(seg_text[:-1])))

                                elif seg_label == 4:  # 열한시
                                    self.uncertain_hour = True
                                    one_datetime.append(Mytime(hour=cardinal_number(seg_text[:-1])))

                                elif seg_label == 5:  # 십삼시/이십사시
                                    one_datetime.append(Mytime(hour=ordinal_number(seg_text[:-1])))


                            elif seg_ner == 'TI_MINUTE':
                                self.minute == True

                                if seg_label == 0:  # 반
                                    one_datetime.append(Mytime(minute=30))

                                elif seg_label == 1:  # nn분
                                    if len(seg_text) == 3:
                                        one_datetime.append(Mytime(minute=int(seg_text[:2])))
                                    else:
                                        one_datetime.append(Mytime(minute=int(seg_text[0])))

                                elif seg_label == 2:
                                    one_datetime.append(Mytime(minute=ordinal_number(seg_text[:-1])))


                            elif seg_ner == 'TI_OTHERS':
                                self.hour = True
                                self.minute = True
                                if seg_label == 0:  # 09:00
                                    self.uncertain_hour = True
                                    tmp = seg_text.split(':')
                                    one_datetime.append(Mytime(hour=int(tmp[0], minute=int(tmp[1]))))
                                elif seg_label == 1:  # 09:00:22
                                    tmp = seg_text.split(':')
                                    one_datetime.append(Mytime(hour=int(tmp[0], minute=int(tmp[1]))))


                        # 기간 부사라면
                        elif segment[1] == False:
                            text = segment[0]
                            adv = segment[2]
                            one_datetime.append(Myadv(text, adv))

                        # 신경쓰지 x
                        else:
                            pass

                if one_datetime:
                    self.sch_list.append(one_datetime)

        # 부사를 포함하여 하나의 datetime 객체로 만들어준다. 이 때의 기준은,
        # 1. 부사와 ti를 기준으로 한 번 나눈다.
        # 1-1. 부사로 한 번 나누고, 그 다음 ti를 기준으로 한 번 나눈다.
        # 2. dt의 우선순위, ti의 우선순위로 나눈다.
        # 2-1. 우선순위가 같은 경우 다른 datetime 객체로 인식.
        # 2-2. 큰 범위(=우선순위가 높은)에 대해 또 언급이 없다면, 그 값을 default로 정한다.
        # 3.when2meet과의 상호작용도 고려하자.

        # sch_list
        # [[단어하나], [(seg1), (seg2)]] :문장 하나
        # [[datetime.timedelta(days=21), (adv: 뒤, index: 21)],
        # [(year: 0, month: 0, week: 0, day: 0, weekday: 2), (adv: 부터, index: 0)],
        # [((hour: 17, minute: 0), (hour: 21, minute: 0))]]

        # tagged_label_list
        # [{'word': '6월 20일', 'ner': 'DT_OTHERS', 'durNpoint': 'POINT', '
        # parsing': [('6월', True, 'DT_MONTH', 'ABS', 1), ('20일', True, 'DT_DAY', 'ABS', 0)]},
        # {'word': '22일', 'ner': 'DT_DAY', 'durNpoint': 'POINT', 'parsing': [('22일', True, 'DT_DAY', 'ABS', 0)]}]

        if tagged_label_list and self.sch_list:

            for one, sch in zip(tagged_label_list, self.sch_list):
                one['sch'] = sch

            tmp = []
            for one in tagged_label_list:
                if len(one['sch']) == 1 and isinstance(one['sch'][0], Myadv):
                    pass
                else:
                    tmp.append(one)

            tagged_label_list = tmp

            former_upper_ner = None
            queue = deque()
            split_TI = []
            tmp = []
            # queue에다가 하나씩 넣다가 마지막 TI가 나오면 모두 pop()
            # TI가 나오면 pop하지만, 뒤에 TI가 있는지 체크 후 pop한다.

            for one in tagged_label_list:
                upper_ner = one['ner']
                if upper_ner[:2] == 'TI':
                    queue.append(one)
                else:
                    if former_upper_ner != None and former_upper_ner[:2] == 'TI':
                        while queue:
                            tmp.append(queue.popleft())
                        split_TI.append(tmp)
                        tmp = []
                    queue.append(one)

                former_upper_ner = upper_ner
            while queue:
                tmp.append(queue.popleft())
            split_TI.append(tmp)

            self.split_time = split_TI

            # 같은 레벨의 DT가 두개 있으면 그 DT 제외 TI까지의 모든 내용을 복제 후 새로운 datetime 객체 하나로 취급해야한다.
            # 이 때, DT의 경우 others가 기간이 아닌 경우인 단어들의 레벨을 알아야 하며,
            # DURATION인 경우 REL인 평일/주말 도 구분해야 한다.
            # TI의 경우도 오전,오후 등의 DURATION도 구분해야 한다.
            priority_DT = {'DT_YEAR': 1, 'DT_MONTH': 2, 'DT_WEEK': 3,
                           'DT_DAY': 4}  # , 'DT_DURATION':3, 'DT_OTHERS': 1 or 2(길이에 따라)
            priority_TI = {'TI_DURATION': 1, 'TI_HOUR': 2, 'TI_MINUTE': 3}  # , 'TI_OTHERS':2

            seperate_datetime = []
            # 1.보다 위의 level이 나오면 아예 다른 datetime으로 분리
            # 2.같을 경우 product를 이용해서 갈라주어야 함.

            # level을 매긴 새로운 list 반환(split2_TI)
            priority_DT = {'DT_YEAR': 1, 'DT_MONTH': 2, 'DT_WEEK': 3, 'DT_DAY': 4}
            priority_TI = {'TI_DURATION': 5, 'TI_OTHERS': 5, 'TI_HOUR': 5, 'TI_MINUTE': 6}
            split2_TI = []

            for one_datetime in split_TI:
                split_level = []
                for idx, one_word in enumerate(one_datetime):
                    upper_ner = one_word['ner']
                    if upper_ner[:2] == 'DT':
                        if upper_ner == 'DT_OTHERS' or upper_ner == 'DT_DURATION':
                            level_check = []
                            for seg in one_word['parsing']:
                                if len(seg) == 5:
                                    if seg[2] == 'DT_DURATION' and seg[3] == 'REL':  # DT_DURATION - 평일, 주말일시 level은 day
                                        level_check.append(priority_DT['DT_DAY'])
                                    elif seg[2] == 'DT_OTHERS' and seg[3] == 'ABS':
                                        level_check.append(priority_DT['DT_MONTH'])
                                    else:
                                        level_check.append(priority_DT[seg[2]])
                            if level_check:
                                level_check = min(level_check)
                            else:
                                level_check = -1
                        else:
                            level_check = priority_DT[upper_ner]
                        split_level.append(level_check)
                    else:  # TI
                        level_check = priority_TI[upper_ner]
                        split_level.append(level_check)

                split2_TI.append(split_level)

            # 1.보다 위의 level이 나오면 아예 다른 datetime으로 분리(split2_TI 이용)
            split_TI3 = []
            split_index = []
            for one_datetime, index in zip(split_TI, split2_TI):
                tmp_datetime = []
                tmp_index = []  # 같은 레벨을 product 해줄 때를 위하여
                former_level = 0
                former_idx = 0
                for i, one_idx in enumerate(index):
                    # 전 값보다 작다면 split
                    if one_idx < former_level:
                        tmp_datetime.append(one_datetime[former_idx:i])
                        tmp_index.append(index[former_idx:i])
                        former_idx = i

                    if len(one_datetime) - 1 == i:
                        tmp_datetime.append(one_datetime[former_idx:i + 1])
                        tmp_index.append(index[former_idx:i + 1])
                    former_level = one_idx

                split_TI3 += tmp_datetime
                split_index += tmp_index
            split_TI = split_TI3

            # 2. 같은 레벨끼리 분류를 하기 위해서 level을 재지정해준다.(others 때문.)
            # weekday 때문에 다시 바꿔야 하나 고민도 듦.
            # 예를 들어 4월 29일부터, 목요일 -> 둘다 day로 취급받아 다른 객체 취급
            priority_DT = {'DT_YEAR': 1, 'DT_MONTH': 2, 'DT_WEEK': 3, 'DT_DURATION': 4, 'DT_OTHERS': 5, 'DT_DAY': 6}
            priority_TI = {'TI_DURATION': 7, 'TI_OTHERS': 7, 'TI_HOUR': 8, 'TI_MINUTE': 9}
            split_index = []

            for one_datetime in split_TI:
                split_level = []
                for idx, one_word in enumerate(one_datetime):
                    upper_ner = one_word['ner']
                    if upper_ner[:2] == 'DT':
                        if upper_ner == 'DT_OTHERS' or upper_ner == 'DT_DURATION':
                            level_check = []
                            for seg in one_word['parsing']:
                                if len(seg) == 5:
                                    level_check.append(priority_DT[seg[2]])
                            if level_check:
                                level_check = max(level_check)
                            else:
                                level_check = -1
                        else:
                            level_check = priority_DT[upper_ner]
                        split_level.append(level_check)
                    else:  # TI
                        level_check = priority_TI[upper_ner]
                        split_level.append(level_check)

                split_index.append(split_level)

            for one_datetime, index in zip(split_TI, split_index):
                tmp = [[] for _ in range(9)]  # 최대 나올 수 있는 level의 수는 9개
                for one_word, idx in zip(one_datetime, index):
                    tmp[idx - 1].append(one_word)
                tmp = [x for x in tmp if x]
                unpack_tuple = [list(x) for x in list(product(*tmp))]
                seperate_datetime += unpack_tuple

            self.sep_datetime = seperate_datetime

            # 부사를 포함하여 하나의 DUR(tuple 형식)으로 만들어 준다.
            # point을 DUR로 만들고, DUR도 DUR로 만든다.

            #  부사를 포함하여 하나의 DUR(tuple 형식)으로 만들어 준다.
            # point도 DUR로 만들고, DUR는 point로 만든다.

            # 1. 모든 point들을 DUR으로 바꾼다.
            for one_datetime in seperate_datetime:
                tmp_one_datetime = []
                for one_word in one_datetime:
                    tuple_one_word = []

                    segments = one_word['sch']
                    for seg in segments:
                        if isinstance(seg, Mydate):
                            tuple_one_word.append((seg, copy.deepcopy(seg)))
                        elif isinstance(seg, Mytime):
                            tuple_one_word.append((seg, copy.deepcopy(seg)))
                        #                             tuple_one_word.append((seg, Mytime()))
                        else:  # Myadv와 이미 duration형태의 꼴들은 그냥 냅둔다.
                            tuple_one_word.append(seg)
                    # 만약 segments에 '~'가 아닌 부사가 앞에 명사 없이 온다면 없애준다.
                    # 헤이 마마

                    if isinstance(tuple_one_word[0], Myadv):
                        if tuple_one_word[0].adv == '~':
                            pass
                        else:
                            tuple_one_word = tuple_one_word[1:]
                    one_word['sch'] = tuple_one_word

            final_datetimes = []
            # 2. word 하나 당 부사를 계산해준다.
            for one_datetime in seperate_datetime:
                words = []
                for one_word in one_datetime:
                    segments = one_word['sch']
                    seg_durNpoint = one_word['durNpoint']
                    upper_ner = one_word['ner']

                    if seg_durNpoint == 'DUR' and len(segments) >= 2:

                        # 부사를 기준으로 앞의 DT나 TI값들을 더해준다. (word 하나임)

                        # 1. 부사를 기준으로 NER 끼리 묶음
                        # [[[(Mydate, Mydate),(Mydate,Mydate)], Myadv, Myadv], [[(Mydate, Mydate),(Mydate,Mydate)]]

                        # queue에다가 하나씩 넣다가 마지막 adv가 나오면 모두 pop()
                        # adv가 나오면 pop하지만, 뒤에 adv가 있는지 체크 후 pop한다.
                        former_class = None
                        queue = deque()
                        split_adv = []
                        tmp = []
                        for seg in segments:
                            if isinstance(seg, Myadv):
                                while queue:
                                    tmp.append(queue.popleft())
                                split_adv.append(tmp)
                                tmp = []
                                split_adv.append(seg)
                            else:
                                queue.append(seg)

                            former_class = seg
                        while queue:
                            tmp.append(queue.popleft())
                        split_adv.append(tmp)

                        split_adv = [x for x in split_adv if x]


                        final_split_adv = []
                        tmp = []
                        queue = deque()
                        former_class = None
                        for lower_one in split_adv:
                            if isinstance(lower_one, list):
                                while queue:
                                    tmp.append(queue.popleft())
                                final_split_adv.append(tmp)
                                tmp = []
                                queue.append(lower_one)
                            else:
                                queue.append(lower_one)

                            former_class = lower_one
                        while queue:
                            tmp.append(queue.popleft())
                        final_split_adv.append(tmp)
                        split_adv = [x for x in final_split_adv if x]


                        # 2. DT나 TI들끼리 계산한다.
                        tmp_split_adv = []
                        for upper_adv_dt in split_adv:
                            tmp = []
                            for adv_datetime in upper_adv_dt:
                                # 만약 adv가 아니라면 연산한다.
                                if isinstance(adv_datetime, list) and isinstance(adv_datetime[0][0], Mydate):
                                    final_begin, final_end = Mydate(), Mydate()
                                    for adv_seg in adv_datetime:
                                        final_begin += adv_seg[0]
                                        final_end += adv_seg[1]
                                    tmp.append((final_begin, final_end))
                                elif isinstance(adv_datetime, list) and isinstance(adv_datetime[0][0], Mytime):
                                    final_begin, final_end = Mytime(), Mytime()
                                    ####찾앗어유
                                    for idx, adv_seg in enumerate(adv_datetime):
                                        final_begin += adv_seg[0]
                                        final_end += adv_seg[1]
                                        if idx == 0 and adv_seg[0].pm == True:
                                            final_begin.pm = True
                                            final_end.pm = True
                                    tmp.append((final_begin, final_end))

                                else:
                                    tmp.append(adv_datetime)

                            tmp_split_adv.append(tmp)


                        # 3. 부사의 값을 연산한다.
                        if upper_ner[:2] == 'DT':

                            # 부터~까지, 부턴~까진, 부터~까진, 부턴~까지, 에서~까지, 월초/말/중(순), 연초/말  (예외) 내내, 동안 -> 애초에 NER에서 표현가능
                            # 둘째주부터 셋째주까지 / 6월초부터 말까지 / 6월 중 /
                            # 부사들의 중요도는 가장 가까이 있는 순부터.
                            # 일단 에서/부터&까지가 같이 있어야 DURATION일 것

                            # NER ~ NER 잊지 말기 -> 이 포맷은 따로 처리해야함 순서대로가 아님.
                            # 큰 범위-> 아래 범위는 동일.(04월1일~2일)

                            # 1. 초,중,말 있는거 계산
                            # 2. '에서,부터,까지' 계산
                            # 3. '~' 계산

                            split_adv = []
                            segments = tmp_split_adv
                            # 6월초부터 같은 말은 두번 돌아야함 6월초/ 부터/ 7월말 /까지

                            for upper_segs in segments:
                                # upper_segs 안에 원하는 부사들이 있다면 or 부사가 없거나 다른 부사만이 있다면
                                flag = False
                                for seg in upper_segs:
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '초' or seg.adv == '중순' or seg.adv == '말':
                                            flag = True

                                if flag:
                                    tmp = []
                                    for idx, seg in enumerate(upper_segs):
                                        if isinstance(seg, Myadv):
                                            att = upper_segs[idx - 1]
                                            if seg.adv == '초':
                                                # 앞이 month라면 10일까지
                                                level = att[0].return_max()
                                                if level == 0:  # 년 -> 1월로
                                                    att[0].month = 1
                                                    att[1].month = 1
                                                    tmp.append(att)

                                                elif level == 1:  # 월 -> 1주로
                                                    att[0].week = 1
                                                    att[1].week = 1
                                                    tmp.append(att)

                                            elif seg.adv == '중순':
                                                # 무조건 월 -> 11에서 22일 사이
                                                att[0].day = 11
                                                att[1].day = 22
                                                tmp.append(att)

                                            elif seg.adv == '말':  ########## 그냥 연말이랑 연초를 따로 빼버려서 추가해야겟음
                                                level = att[0].return_max()
                                                if level == 0:  # 년 -> 12월로
                                                    att[0].month = 12
                                                    att[1].month = 12
                                                    tmp.append(att)

                                                elif level == 1:  # 월 -> 마지막 10일 정도로
                                                    y, m = att[0].year, att[0].month
                                                    if y == 0:
                                                        y = dt.datetime.now().year
                                                    if m == 0:
                                                        m = dt.datetime.now().month + 1
                                                    else:
                                                        m += 1
                                                    last_day = (dt.datetime(y, m, 1) - dt.timedelta(days=1)).day
                                                    att[0].day = last_day - 10
                                                    att[1].day = last_day
                                                    tmp.append(att)

                                            else:  # 나머지 부사의 경우
                                                tmp.append(seg)
                                    split_adv.append(tmp)
                                else:
                                    split_adv.append(upper_segs)


                            ################# 부사부분 단어 level flag 맞춰줘야됨
                            segments = split_adv
                            split_adv = []

                            for upper_segs in segments:
                                flag = False
                                for seg in upper_segs:
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '이후' or seg.adv == '후' or seg.adv == '뒤' or seg.adv == '이전' or seg.adv == '전' or seg.adv == '이내' or seg.adv == '안' or seg.adv == '내':
                                            flag = True
                                if flag:
                                    tmp = []
                                    for idx, seg in enumerate(upper_segs):
                                        if isinstance(seg, Myadv):
                                            att = upper_segs[idx - 1]
                                            if seg.adv == '이후' or seg.adv == '후' or seg.adv == '뒤':
                                                tmp_dt = Mydate(after=1)
                                                tmp_dt.set_flag(*att[1].all_flag_list)
                                                tmp.append((att[1], tmp_dt))
                                            elif seg.adv == '이전' or seg.adv == '전' or seg.adv == '이내' or seg.adv == '안' or seg.adv == '내':
                                                # 뒤의 값은 set해놓고, 앞의 값은 Mydate()로
                                                tmp_dt = Mydate(before=1)
                                                tmp_dt.set_flag(*att[0].all_flag_list)
                                                tmp.append((tmp_dt, att[0]))
                                            else:
                                                tmp.append(seg)
                                    split_adv.append(tmp)
                                else:
                                    split_adv.append(upper_segs)


                            segments = split_adv
                            split_adv = []

                            for upper_segs in segments:
                                flag = False
                                for seg in upper_segs:
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '에서' or seg.adv == '에선' or seg.adv == '부터' or seg.adv == '부턴' or seg.adv == '까지' or seg.adv == '까진' or seg.adv == '~':
                                            flag = True
                                if flag:
                                    for idx, seg in enumerate(upper_segs):
                                        if isinstance(seg, Myadv):
                                            att = upper_segs[idx - 1]
                                            if seg.adv == '에서' or seg.adv == '에선' or seg.adv == '부터' or seg.adv == '부턴':
                                                tmp_dt = Mydate(after=1)

                                                split_adv.append((att[0], tmp_dt))
                                            elif seg.adv == '까지' or seg.adv == '까진':
                                                tmp_dt = Mydate(before=1)

                                                split_adv.append((tmp_dt, att[1]))
                                            elif seg.adv == '~':
                                                split_adv += upper_segs
                                #                                 else:  # 나머지 부사의 경우 단순 추가
                                #                                     split_adv.append(seg)
                                else:
                                    split_adv += upper_segs


                            segments = split_adv
                            split_adv = []

                            flag = False
                            for seg in segments:
                                if isinstance(seg, Myadv):
                                    if seg.adv == '~':
                                        flag = True
                            # 만약 ~가 안에 있다면
                            if flag:
                                for idx, seg in enumerate(segments):
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '~':
                                            if idx == 0:
                                                after_att = segments[idx + 1]
                                                tmp_dt = Mydate(before=1)
                                                tmp_dt.set_flag(*after_att[0].all_flag_list)
                                                split_adv.append((tmp_dt, after_att[0]))
                                            elif idx == len(segments) - 1:
                                                before_att = segments[idx - 1]
                                                tmp_dt = Mydate(after=1)
                                                tmp_dt.set_flag(*before_att[1].all_flag_list)
                                                split_adv.append((before_att[1], Mydate(after=1)))
                                            else:  # 앞의 첫값을, 뒤의 뒷값을 갖고 와서 set
                                                before_att = segments[idx - 1]
                                                after_att = segments[idx + 1]
                                                split_adv.append((before_att[0], after_att[1]))

                                begin, end = Mydate(), Mydate()
                                for seg in split_adv:
                                    begin += seg[0]
                                    end += seg[1]
                            else:
                                begin, end = Mydate(), Mydate()

                                for seg in segments:
                                    begin += seg[0]
                                    end += seg[1]

                        #                 words.append((begin,end))

                        else:  # TI일 때
                            split_adv = []
                            segments = tmp_split_adv

                            split_adv = []
                            for upper_segs in segments:
                                flag = False
                                for seg in upper_segs:
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '이후' or seg.adv == '후' or seg.adv == '뒤' or seg.adv == '이전' or seg.adv == '전' or seg.adv == '이내' or seg.adv == '안' or seg.adv == '내':
                                            flag = True
                                if flag:
                                    tmp = []
                                    for idx, seg in enumerate(upper_segs):
                                        if isinstance(seg, Myadv):
                                            att = upper_segs[idx - 1]
                                            if seg.adv == '이후' or seg.adv == '후' or seg.adv == '뒤':
                                                # 앞의 값의 첫값은 set해놓고, 뒤의 값은 Mytime()로
                                                tmp.append((att[1], Mytime(24)))
                                            elif seg.adv == '이전' or seg.adv == '전' or seg.adv == '이내' or seg.adv == '안' or seg.adv == '내':
                                                # 뒤의 값은 set해놓고, 앞의 값은 Mydate()로
                                                tmp.append((Mytime(0), att[0]))
                                            else:
                                                tmp.append(seg)
                                    split_adv += tmp
                                else:
                                    split_adv.append(upper_segs)


                            count = 0
                            for type_ in split_adv:
                                if isinstance(type_, Myadv):
                                    count += 1
                            if count:
                                split_adv = [split_adv]

                            segments = split_adv
                            split_adv = []

                            for upper_segs in segments:
                                flag = False

                                for seg in upper_segs:
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '에서' or seg.adv == '에선' or seg.adv == '부터' or seg.adv == '부턴' or seg.adv == '까지' or seg.adv == '까진' or seg.adv == '~':
                                            flag = True
                                if flag:
                                    for idx, seg in enumerate(upper_segs):
                                        if isinstance(seg, Myadv):
                                            att = upper_segs[idx - 1]
                                            if seg.adv == '에서' or seg.adv == '에선' or seg.adv == '부터' or seg.adv == '부턴':
                                                split_adv.append((att[0], Mytime(24)))
                                            elif seg.adv == '까지' or seg.adv == '까진':
                                                split_adv.append((Mytime(0), att[1]))
                                            elif seg.adv == '~':
                                                split_adv += upper_segs
                                #                                 else:  # 나머지 부사의 경우 단순 추가
                                #                                     split_adv.append(seg)
                                else:
                                    split_adv.append(upper_segs)

                            # ~값을 계산후 총 하나로
                            segments = split_adv
                            split_adv = []

                            flag = False
                            for seg in segments:
                                if isinstance(seg, Myadv):
                                    if seg.adv == '~':
                                        flag = True

                            # 만약 ~가 안에 있다면
                            if flag:
                                for idx, seg in enumerate(segments):
                                    if isinstance(seg, Myadv):
                                        if seg.adv == '~':
                                            if idx == 0:
                                                after_att = segments[idx + 1]
                                                split_adv.append((Mytime(), after_att[0]))
                                            elif idx == len(segments):
                                                before_att = segments[idx - 1]
                                                split_adv.append((before_att[1], Mytime()))
                                            else:  # 앞의 첫값을, 뒤의 뒷값을 갖고 와서 set
                                                before_att = segments[idx - 1]
                                                after_att = segments[idx + 1]
                                                split_adv.append((before_att[0], after_att[1]))

                                begin, end = Mytime(), Mytime()
                                for seg in split_adv:
                                    begin += seg[0]
                                    end += seg[1]
                            else:
                                begin, end = Mytime(), Mytime()
                                for seg in segments:
                                    begin += seg[0]
                                    end += seg[1]

                        #                 words.append((begin,end))
                        words.append((begin, end))



                    else:  # POINT일시 sch 그대로 반환
                        #             if len(segments) >= 2:  # 다른 레벨의 값이 같이 있는 것
                        if upper_ner[:2] == 'DT':
                            begin, end = Mydate(), Mydate()
                            for seg in segments:
                                begin += seg[0]
                                end += seg[1]
                        else:
                            begin, end = Mytime(), Mytime()
                            for idx, seg in enumerate(segments):
                                begin += seg[0]
                                end += seg[1]
                                if idx == 0 and seg[0].pm == True:
                                    begin.pm = True
                                    end.pm = True

                        words.append((begin, end))
                final_datetimes.append(words)


            real_final_datetimes = []
            for one_datetime in final_datetimes:
                begin_DT, end_DT = Mydate(), Mydate()
                begin_TI, end_TI = Mytime(), Mytime()
                count_ti = 0
                for one_class in one_datetime:
                    if isinstance(one_class[0], Mydate):
                        begin_DT += one_class[0]
                        end_DT += one_class[1]
                    else:
                        begin_TI += one_class[0]
                        end_TI += one_class[1]
                        if count_ti == 0 and one_class[0].pm == True:
                            begin_TI.pm = True
                            end_TI.pm = True
                        count_ti += 1
                real_final_datetimes.append((begin_DT, end_DT, begin_TI, end_TI))

            self.raw_datetime = real_final_datetimes


            re_tmp = []
            for one_datetime in real_final_datetimes:
                re_tmp += self.calculate_days(one_datetime)

            self.refined_datetime = re_tmp

            self.split_day()

    def __repr__(self):
        return f'operator : {self.operator}  label_list : {self.refined_datetime}'

    def calculate_days(self, one_datetime):
        calculated_datetime = []
        # input: (begin_DT, end_DT, begin_TI, end_TI)
        (begin_DT, end_DT, begin_TI, end_TI) = one_datetime

        # 고려해야 할게, '부터'나 '까지'의 경우 또는 아예 없는 경우(=모두 된다는 뜻)은 모두 비어있음
        # 이런 경우 index = 5.
        # 다 채워져 있으면 index가 5

        begin_DT_index = begin_DT.return_min()
        end_DT_index = end_DT.return_min()

        # 1.두개를 비교해서 index가 차이가 난다면(높은값만), 일단 그 값을 먼저 평탄하게 해주자
        if begin_DT_index != 5 and end_DT_index != 5:
            tmp = []
            if begin_DT_index > end_DT_index:  # begin_DT가 설정이 안된 값이 있으면 값을 채워줌
                if begin_DT.before == 0:  # '까지' 가 아닐 경우
                    for idx, (b, e) in enumerate(zip(begin_DT.all_list, end_DT.all_list)):
                        if idx < begin_DT_index and idx >= end_DT_index:
                            tmp.append(e)
                        else:
                            tmp.append(b)
                    tmp_flag = begin_DT.all_flag_list
                    begin_DT = Mydate(tmp[0], tmp[1], tmp[2], tmp[3], tmp[4], tmp[5], tmp[6])
                    begin_DT.set_flag(*tmp_flag)
                    begin_DT_index = begin_DT.return_min()
                else:
                    # default로 나온 값 중 가장 작은 값. or 없으면 오늘.
                    pass
            elif begin_DT_index < end_DT_index:
                if end_DT.after == 0:  # '부터' 가 아닐 경우
                    for idx, (b, e) in enumerate(zip(begin_DT.all_list, end_DT.all_list)):
                        if idx >= begin_DT_index and idx < end_DT_index:
                            tmp.append(b)
                        else:
                            tmp.append(e)
                    tmp_flag = end_DT.all_flag_list
                    end_DT = Mydate(tmp[0], tmp[1], tmp[2], tmp[3], tmp[4], tmp[5], tmp[6])
                    end_DT.set_flag(*tmp_flag)
                    end_DT_index = end_DT.return_min()
                else:
                    # default로 나온 값 중 가장 큰 값 or 한달 뒤
                    pass

        upper = min(begin_DT_index, end_DT_index)

        # 2-1.더 큰 level 값들을 when2meet class를 가서 받아온다.
        if upper != 0 and upper != 5:
            result = speakers[self.name].check_default_DT(upper)
            if upper == 4:  # 아무 것도 없고 요일만 있을 때
                if result[3]:  # week가 있다면 week까지만 채워준다
                    result_begin = result[:3] + begin_DT.all_list[3:]
                    result_end = result[:3] + end_DT.all_list[3:]
                else:  # week가 없다면 day까지 채워준다.
                    result_begin = result[:4] + begin_DT.all_list[4:]
                    result_end = result[:4] + end_DT.all_list[4:]

            else:
                result_begin = result + begin_DT.all_list[upper:]
                result_end = result + end_DT.all_list[upper:]

            tmp_flag = begin_DT.all_flag_list
            begin_DT = Mydate(result_begin[0], result_begin[1], result_begin[2], result_begin[3], result_begin[4])
            begin_DT.set_flag(*tmp_flag)
            begin_DT.before = result_begin[5]

            tmp_flag = end_DT.all_flag_list
            end_DT = Mydate(result_end[0], result_end[1], result_end[2], result_end[3], result_end[4])
            end_DT.set_flag(*tmp_flag)
            end_DT.after = result_end[6]

        # 2-2. 부터,까지의 값들을 default값 아님 현재 날짜에 맞춰 채운다. 일단 걍 오늘, 한달 뒤로 채움.
        if begin_DT.before and not end_DT.after:  # 까지의 경우
            # 지금은 오늘로 채움
            tmp_flag = end_DT.all_flag_list
            begin_DT = Mydate(year=self.now.year, month=self.now.month, day=self.now.day, before=1)
            begin_DT.set_flag(*tmp_flag)

        elif end_DT.after and not begin_DT.before:  # 부터의 경우
            if begin_DT.month:
                if begin_DT.week or begin_DT.day:
                    if begin_DT.day:  # begin이 day까지만 있는 경우
                        tmp_flag = begin_DT.all_flag_list
                        tmp = dt.datetime(begin_DT.year, begin_DT.month, begin_DT.day) + dt.timedelta(days=30)
                        end_DT = Mydate(year=tmp.year, month=tmp.month, day=tmp.day, weekday=end_DT.weekday, after=1)
                        end_DT.set_flag(*tmp_flag)
                    else:  # begin이 week까지만 있는 경우(+weekday)
                        if begin_DT.month == 12:
                            tmp_flag = begin_DT.all_flag_list
                            end_DT = Mydate(year=begin_DT.year + 1, month=1, day=begin_DT.day, weekday=end_DT.weekday,
                                            after=1)
                            end_DT.set_flag(*tmp_flag)
                        else:
                            tmp_flag = begin_DT.all_flag_list
                            end_DT = Mydate(year=begin_DT.year, month=begin_DT.month + 1, day=begin_DT.day,
                                            weekday=end_DT.weekday, after=1)
                            end_DT.set_flag(*tmp_flag)
                else:  # begin이 month까지만 있는 경우(+weekday)
                    tmp_flag = begin_DT.all_flag_list
                    end_DT = Mydate(year=begin_DT.year, month=12, day=31, weekday=end_DT.weekday, after=1)
                    end_DT.set_flag(*tmp_flag)

            begin_DT.print_flags()
            end_DT.print_flags()

        # 사실 TI는 거의 절대 그런 경우가 나오지 않기 때문에 굳이 안해도 된다.

        # 3. 값들이 다 set 되었으므로 month, week, weekday를 day로 통일시킨다.
        # 3-1. month는 있는데, 그 뒤로 쭉 비어 있을 경우, day를 1~마지막날로 set한다.
        # 3-2. week 계산 -> 3-2-1. DAY가 있으면 DAY를 우선한다. 3-2-2. 없으면 DAY로 set
        # 3-3. weekday 계산 -> DAY가 안에 있는 값들 중 weekday를 고른다.

        # 3-1 month는 있는데, 그 뒤로 쭉 비어 있을 경우, day를 1~마지막날로 set한다.
        if begin_DT.return_max() == 1:
            begin_DT.day = 1
        if end_DT.return_max() == 1:
            end_year, end_month = end_DT.year, end_DT.month
            tmp = (dt.datetime(end_year, end_month + 1, 1) - dt.timedelta(days=1)).day
            end_DT.day = tmp
        # 3-1-2 weekday, month는 있는데 week, day가 없는 경우
        if begin_DT.return_max() == 4 and not begin_DT.week and not begin_DT.day:
            begin_DT.day = 1
        if end_DT.return_max() == 4 and not end_DT.week and not end_DT.day:
            tmp = (dt.datetime(end_DT.year, end_DT.month + 1, 1) - dt.timedelta(days=1)).day
            end_DT.day = tmp

        # 3-2 :week 계산
        if begin_DT.return_max() == 2:

            month_1st = dt.datetime(begin_DT.year, begin_DT.month, 1).weekday()
            month_last = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=1)).weekday()

            one_week = dt.datetime(begin_DT.year, begin_DT.month, 1) - dt.timedelta(days=month_1st)
            last_week = dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=month_last + 1)

            if begin_DT.week == 100:  # 마지막주
                tmp_dt = begin_DT.all_flag_list
                begin_DT = Mydate(year=last_week.year, month=last_week.month, day=last_week.day, before=begin_DT.before)
                begin_DT.set_flag(*tmp_dt)
            else:
                one_week = one_week + dt.timedelta(days=7 * (begin_DT.week - 1))
                tmp_dt = begin_DT.all_flag_list
                begin_DT = Mydate(year=one_week.year, month=one_week.month, day=one_week.day, before=begin_DT.before)
                begin_DT.set_flag(*tmp_dt)

        if end_DT.return_max() == 2:
            month_1st = dt.datetime(end_DT.year, end_DT.month, 1).weekday()
            month_1st = 6 - month_1st
            month_last = (dt.datetime(end_DT.year, end_DT.month + 1, 1) - dt.timedelta(days=1)).weekday()
            month_last = 6 - month_last

            one_week = dt.datetime(end_DT.year, end_DT.month, 1) + dt.timedelta(days=month_1st)
            last_week = dt.datetime(end_DT.year, end_DT.month + 1, 1) + dt.timedelta(days=month_last - 1)

            if end_DT.week == 100:  # 마지막주
                tmp_dt = end_DT.all_flag_list
                end_DT = Mydate(year=last_week.year, month=last_week.month, day=last_week.day, after=end_DT.after)
                end_DT.set_flag(*tmp_dt)
            else:
                one_week = one_week + dt.timedelta(days=7 * (end_DT.week - 1))
                tmp_dt = end_DT.all_flag_list
                end_DT = Mydate(year=one_week.year, month=one_week.month, day=one_week.day, after=end_DT.after)
                end_DT.set_flag(*tmp_dt)

        # day는 설정이 안되어있고, weekday랑 week만 되어 있는 경우 -> 단순히 day로 바꿔준다. (뒤에서 weekday 연산)
        if begin_DT.return_max() == 4 and begin_DT.day == 0 and begin_DT.week:
            month_1st = dt.datetime(begin_DT.year, begin_DT.month, 1).weekday()
            month_last = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=1)).weekday()

            one_week = dt.datetime(begin_DT.year, begin_DT.month, 1) - dt.timedelta(days=month_1st)
            last_week = dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=month_last + 1)

            if begin_DT.week == 100:  # 마지막주
                tmp_dt = begin_DT.all_flag_list
                begin_DT = Mydate(year=last_week.year, month=last_week.month, day=last_week.day,
                                  weekday=begin_DT.weekday, before=begin_DT.before)
                begin_DT.set_flag(*tmp_dt)
            else:
                one_week = one_week + dt.timedelta(days=7 * (begin_DT.week - 1))
                tmp_dt = begin_DT.all_flag_list
                begin_DT = Mydate(year=one_week.year, month=one_week.month, day=one_week.day, weekday=begin_DT.weekday,
                                  before=begin_DT.before)
                begin_DT.set_flag(*tmp_dt)

        if end_DT.return_max() == 4 and end_DT.day == 0 and end_DT.week:
            month_1st = dt.datetime(end_DT.year, end_DT.month, 1).weekday()
            month_1st = 6 - month_1st
            month_last = (dt.datetime(end_DT.year, end_DT.month + 1, 1) - dt.timedelta(days=1)).weekday()
            month_last = 6 - month_last

            one_week = dt.datetime(end_DT.year, end_DT.month, 1) + dt.timedelta(days=month_1st)
            last_week = dt.datetime(end_DT.year, end_DT.month + 1, 1) + dt.timedelta(days=month_last - 1)

            if end_DT.week == 100:  # 마지막주
                tmp_dt = end_DT.all_flag_list
                end_DT = Mydate(year=last_week.year, month=last_week.month, day=last_week.day, weekday=end_DT.weekday,
                                after=end_DT.after)
                end_DT.set_flag(*tmp_dt)
            else:
                one_week = one_week + dt.timedelta(days=7 * (end_DT.week - 1))
                tmp_dt = end_DT.all_flag_list
                end_DT = Mydate(year=one_week.year, month=one_week.month, day=one_week.day, weekday=end_DT.weekday,
                                after=end_DT.after)
                end_DT.set_flag(*tmp_dt)

        if begin_DT.return_max() == 4 and begin_DT.week == 0 and begin_DT.day == 0:  # 6월 월요일마다
            begin_DT.day = 1
        if begin_DT.return_max() == 4 and begin_DT.week == 0 and begin_DT.day == 0:  # 달마다
            end_year, end_month = end_DT.year, end_DT.month
            tmp = (dt.datetime(end_year, end_month + 1, 1) - dt.timedelta(days=1)).day
            end_DT.day = tmp

        # 3-3 -> day기반으로 동작하는 weekday
        # input은 year, month, day, weekday가 있다고 가정한다.
        weekday_list = []
        add_weekday_list = []
        if begin_DT.return_max() == 4 and end_DT.return_max() == 4:
            begin_day, end_day = begin_DT.day, end_DT.day
            begin_weekday, end_weekday = begin_DT.weekday, end_DT.weekday
            b_flag, e_flag = begin_DT.all_flag_list, end_DT.all_flag_list

            if begin_DT.month != end_DT.month:  # 달이 넘어가버렸음.
                # 마지막 날
                # 첫달이랑, 막달만 각각 day check해주고,
                # 사이달은 1일에서 끝일까지 찾기

                tmp = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=1)).day
                for i in range(begin_day, tmp + 1):
                    tmp_day = dt.datetime(begin_DT.year, begin_DT.month, i).weekday()
                    if tmp_day >= begin_weekday and tmp_day <= end_weekday:
                        tmp_b, tmp_e = Mydate(begin_DT.year, begin_DT.month, 0, i), Mydate(begin_DT.year,
                                                                                           begin_DT.month, 0, i)
                        tmp_b.set_flag(*b_flag)
                        tmp_e.set_flag(*e_flag)
                        weekday_list.append((tmp_b, tmp_e, begin_TI, end_TI))

                if end_DT.month - begin_DT.month > 1:
                    for i in range(begin_DT.month + 1, end_DT.month):
                        tmp = (dt.datetime(begin_DT.year, i + 1, 1) - dt.timedelta(days=1)).day
                        for j in range(1, tmp + 1):
                            tmp_day = dt.datetime(begin_DT.year, i, j).weekday()
                            if tmp_day >= begin_weekday and tmp_day <= end_weekday:
                                tmp_b, tmp_e = Mydate(begin_DT.year, i, 0, j), Mydate(begin_DT.year, i, 0, j)
                                tmp_b.set_flag(*b_flag)
                                tmp_e.set_flag(*e_flag)
                                weekday_list.append((tmp_b, tmp_e, begin_TI, end_TI))

                for i in range(1, end_day + 1):
                    tmp_day = dt.datetime(end_DT.year, end_DT.month, i).weekday()
                    if tmp_day >= begin_weekday and tmp_day <= end_weekday:
                        tmp_b, tmp_e = Mydate(end_DT.year, end_DT.month, 0, i), Mydate(end_DT.year, end_DT.month, 0, i)
                        tmp_b.set_flag(*b_flag)
                        tmp_e.set_flag(*e_flag)
                        add_weekday_list.append((tmp_b, tmp_e, begin_TI, end_TI))

            else:
                for i in range(begin_day, end_day + 1):
                    tmp_day = dt.datetime(begin_DT.year, begin_DT.month, i).weekday()
                    if tmp_day >= begin_weekday and tmp_day <= end_weekday:
                        tmp_b, tmp_e = Mydate(begin_DT.year, begin_DT.month, 0, i), Mydate(end_DT.year, end_DT.month, 0,
                                                                                           i)
                        tmp_b.set_flag(*b_flag)
                        tmp_e.set_flag(*e_flag)
                        weekday_list.append((tmp_b, tmp_e, begin_TI, end_TI))
        if weekday_list:
            calculated_datetime += weekday_list
            calculated_datetime += add_weekday_list
        else:
            calculated_datetime.append((begin_DT, end_DT, begin_TI, end_TI))

        return calculated_datetime

    def split_day(self):
        split_day_datetime = []
        for one_datetime in self.refined_datetime:
            begin_DT, end_DT, begin_TI, end_TI = one_datetime
            b_flag, e_flag = begin_DT.all_flag_list, end_DT.all_flag_list

            if begin_DT.month != end_DT.month:  # 다른 달
                # 달 단위로 끊어서
                # DAY가 1이상 차이나면 split.
                tmp = (dt.datetime(begin_DT.year, begin_DT.month + 1, 1) - dt.timedelta(days=1)).day
                for i in range(begin_DT.day, tmp + 1):
                    tmp_b, tmp_e = Mydate(begin_DT.year, begin_DT.month, 0, i), Mydate(begin_DT.year, begin_DT.month, 0,
                                                                                       i)
                    tmp_b.set_flag(*b_flag)
                    tmp_e.set_flag(*e_flag)
                    split_day_datetime.append((tmp_b, tmp_e, begin_TI, end_TI))

                if end_DT.month - begin_DT.month > 1:
                    for i in range(begin_DT.month + 1, end_DT.month):
                        tmp = (dt.datetime(begin_DT.year, i + 1, 1) - dt.timedelta(days=1)).day
                        for j in range(1, tmp + 1):
                            tmp_b, tmp_e = Mydate(begin_DT.year, i, 0, j), Mydate(begin_DT.year, i, 0, j)
                            tmp_b.set_flag(*b_flag)
                            tmp_e.set_flag(*e_flag)
                            split_day_datetime.append((tmp_b, tmp_e, begin_TI, end_TI))

                for i in range(1, end_DT.day + 1):
                    tmp_b, tmp_e = Mydate(begin_DT.year, end_DT.month, 0, i), Mydate(begin_DT.year, end_DT.month, 0, i)
                    tmp_b.set_flag(*b_flag)
                    tmp_e.set_flag(*e_flag)
                    split_day_datetime.append((tmp_b, tmp_e, begin_TI, end_TI))

            else:  # 같은 달
                # DAY가 1이상 차이나면 split.
                for i in range(begin_DT.day, end_DT.day + 1):
                    tmp_b, tmp_e = Mydate(begin_DT.year, begin_DT.month, 0, i), Mydate(end_DT.year, end_DT.month, 0, i)
                    tmp_b.set_flag(*b_flag)
                    tmp_e.set_flag(*e_flag)
                    split_day_datetime.append((tmp_b, tmp_e, begin_TI, end_TI))

        for one_datetime in split_day_datetime:
            begin_DT, end_DT, begin_TI, end_TI = one_datetime
            if begin_TI.hour == -1:
                begin_TI.hour = 0
            if end_TI.hour == -1:
                end_TI.hour = 24

        self.refined_datetime = split_day_datetime
