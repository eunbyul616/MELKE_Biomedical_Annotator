def wordCound(sentence):
    # 입력 : 문장
    # return : (1) word 단위로 잘린 list (2) 입력으로 들어 온 문장 내 character 수
    words = sentence.split()
    charLen = len(sentence)
    return words, charLen

def senNum(sen, senCharLen, charBegin, charEnd):
    # 입력 : sen, senCharLen, 찾고자하는 단어의 charBegin, charEnd
    # return : 문장 number (id), 문장 내 character begin, 문장 내 char End
    begin = charBegin
    end = charEnd
    i = 0

    for i in range(len(sen)):
        # print("SenNum", i)
        # print("B / E", begin, end)
        # print("senCharLen ", senCharLen[i])
        if begin > senCharLen[i] + i:
            # 현재 문장이 찾는 word의 문장이 아닌 경우
            begin -= senCharLen[i]
            end -= senCharLen[i]
        else:
            break
    return i, begin, end

def wordNum(sentence, senNum, charBegin, charEnd, word):
    # sentence : word 별로 잘린 list
    # sentence Number

    begin = charBegin
    end = charEnd
    i = 0

    if senNum != 0:
        begin -= senNum + 1
        end -= senNum + 1

    for i in range(len(sentence)):
        if begin > len(sentence[i]):
            begin -= len(sentence[i]) + 1
            end -= len(sentence[i]) + 1
        else:
            break

    if len(word.split()) != 1:
        return i, i+len(word.split())-1
    else:
        return i, i