INITIAL='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
VOWEL='ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
FINAL=' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'
CV={p[:2]:p[2] for p in ['ㅗㅏㅘ','ㅗㅐㅙ','ㅗㅣㅚ','ㅜㅓㅝ','ㅜㅔㅞ','ㅜㅣㅟ','ㅡㅣㅢ']}
CF={p[:2]:p[2] for p in ['ㄱㅅㄳ','ㄴㅈㄵ','ㄴㅎㄶ','ㄹㄱㄺ','ㄹㅁㄻ','ㄹㅂㄼ','ㄹㅅㄽ','ㄹㅌㄾ','ㄹㅍㄿ','ㄹㅎㅀ','ㅂㅅㅄ']}
LATIN=dict(zip('rsefaqtdwczxvgkoijpu hynbml'.replace(' ',''),'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㅏㅐㅑㅓㅔㅕㅗㅛㅜㅠㅡㅣ'))
LATIN.update(dict(zip('REQTWO P'.replace(' ',''),'ㄲㄸㅃㅆㅉㅒㅖ')))
def jamo(c):return LATIN.get(c,LATIN.get(c.lower(),c))
def compose(s):
 out='';i=0
 while i<len(s):
  c=s[i]
  if c not in INITIAL or i+1>=len(s) or s[i+1] not in VOWEL:
   if c in VOWEL and i+1<len(s) and s[i:i+2] in CV:out+=CV[s[i:i+2]];i+=2
   else:out+=c;i+=1
   continue
  l=INITIAL.index(c);v=s[i+1];i+=2
  if i<len(s) and v+s[i] in CV:v=CV[v+s[i]];i+=1
  t=0
  if i<len(s) and s[i] in FINAL[1:] and (i+1>=len(s) or s[i+1] not in VOWEL):
   f=s[i];t=FINAL.index(f);i+=1
   if i<len(s) and f+s[i] in CF and (i+1>=len(s) or s[i+1] not in VOWEL):t=FINAL.index(CF[f+s[i]]);i+=1
  out+=chr(0xac00+(l*21+VOWEL.index(v))*28+t)
 return out
