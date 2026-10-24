"""
PESE NLP: Stemmer
Clean, deterministic implementation of Martin Porter's 1980 stemming algorithm.
Zero external runtime dependencies.
"""

from typing import List
from functools import lru_cache


IRREGULAR_LEMMAS = {
    "weight": "weigh",
    "weights": "weigh",
    "bought": "buy",
    "went": "go",
    "gone": "go",
    "wrote": "write",
    "written": "write",
    "built": "build",
    "taught": "teach",
    "thought": "think",
    "caught": "catch",
    "brought": "bring",
    "found": "find",
    "came": "come",
    "took": "take",
    "taken": "take",
    "saw": "see",
    "seen": "see",
    "rode": "ride",
    "ridden": "ride",
    "learnt": "learn",
    "paid": "pay",
}


class PorterStemmer:
    """
    Porter Stemming Algorithm.
    Original paper: Porter, 1980, 'An algorithm for suffix stripping', Program, 14(3), pp 130-137.
    """

    def __init__(self):
        self.b = ""  # buffer for word to be stemmed
        self.k = 0
        self.k0 = 0
        self.j = 0  # general offset into the string

    def _is_consonant(self, i: int) -> bool:
        """True <=> b[i] is a consonant."""
        ch = self.b[i]
        if ch in ('a', 'e', 'i', 'o', 'u'):
            return False
        if ch == 'y':
            if i == self.k0:
                return True
            else:
                return not self._is_consonant(i - 1)
        return True

    def _measure(self) -> int:
        """
        Measures the number of consonant sequences between k0 and j.
        If c is a consonant sequence and v a vowel sequence, then:
        <c><v>       gives 0
        <c>vc<v>     gives 1
        <c>vcvc<v>   gives 2
        <c>vcvcvc<v> gives 3
        """
        n = 0
        i = self.k0
        while True:
            if i > self.j:
                return n
            if not self._is_consonant(i):
                break
            i += 1
        i += 1
        while True:
            while True:
                if i > self.j:
                    return n
                if self._is_consonant(i):
                    break
                i += 1
            i += 1
            n += 1
            while True:
                if i > self.j:
                    return n
                if not self._is_consonant(i):
                    break
                i += 1
            i += 1

    def _vowel_in_stem(self) -> bool:
        """True <=> k0,...j contains a vowel."""
        for i in range(self.k0, self.j + 1):
            if not self._is_consonant(i):
                return True
        return False

    def _double_consonant(self, i: int) -> bool:
        """True <=> i,(i-1) contain a double consonant."""
        if i < self.k0 + 1:
            return False
        if self.b[i] != self.b[i - 1]:
            return False
        return self._is_consonant(i)

    def _cvc(self, i: int) -> bool:
        """
        True <=> i-2,i-1,i has the form consonant - vowel - consonant
        and also if the second c is not w,x or y. this is used when trying to
        restore an e at the end of a short word. e.g.
           cav(e), lov(e), hop(e), crim(e), but
           snow, box, tray.
        """
        if i < self.k0 + 2 or not self._is_consonant(i) or self._is_consonant(i - 1) or not self._is_consonant(i - 2):
            return False
        ch = self.b[i]
        if ch in ('w', 'x', 'y'):
            return False
        return True

    def _ends(self, s: str) -> bool:
        """True <=> k0,...k ends with the string s."""
        length = len(s)
        o = self.k - length + 1
        if o < self.k0:
            return False
        if self.b[o:o + length] != s:
            return False
        self.j = self.k - length
        return True

    def _set_to(self, s: str) -> None:
        """Sets (j+1),...k to the characters in the string s, readjusting k."""
        length = len(s)
        o = self.j + 1
        self.b = self.b[:o] + s + self.b[o + length:]
        self.k = self.j + length

    def _r(self, s: str) -> None:
        if self._measure() > 0:
            self._set_to(s)

    def _step1ab(self) -> None:
        """Step 1ab gets rid of plurals and -ed or -ing."""
        if self.b[self.k] == 's':
            if self._ends("sses"):
                self.k = self.k - 2
            elif self._ends("ies"):
                self._set_to("i")
            elif self.b[self.k - 1] != 's':
                self.k = self.k - 1

        if self._ends("eed"):
            if self._measure() > 0:
                self.k = self.k - 1
        elif (self._ends("ed") or self._ends("ing")) and self._vowel_in_stem():
            self.k = self.j
            if self._ends("at"):
                self._set_to("ate")
            elif self._ends("bl"):
                self._set_to("ble")
            elif self._ends("iz"):
                self._set_to("ize")
            elif self._double_consonant(self.k):
                self.k = self.k - 1
                ch = self.b[self.k]
                if ch in ('l', 's', 'z'):
                    self.k = self.k + 1
            elif self._measure() == 1 and self._cvc(self.k):
                self._set_to("e")

    def _step1c(self) -> None:
        """Step 1c turns terminal y to i when there is another vowel in the stem."""
        if self._ends("y") and self._vowel_in_stem():
            self.b = self.b[:self.k] + 'i' + self.b[self.k + 1:]

    def _step2(self) -> None:
        """Step 2 maps double suffices to single ones."""
        if self.k <= self.k0:
            return
        ch = self.b[self.k - 1]
        if ch == 'a':
            if self._ends("ational"):
                self._r("ate")
            elif self._ends("tional"):
                self._r("tion")
        elif ch == 'c':
            if self._ends("enci"):
                self._r("ence")
            elif self._ends("anci"):
                self._r("ance")
        elif ch == 'e':
            if self._ends("izer"):
                self._r("ize")
        elif ch == 'l':
            if self._ends("bli"):
                self._r("ble")
            elif self._ends("alli"):
                self._r("al")
            elif self._ends("entli"):
                self._r("ent")
            elif self._ends("eli"):
                self._r("e")
            elif self._ends("ousli"):
                self._r("ous")
        elif ch == 'o':
            if self._ends("ization"):
                self._r("ize")
            elif self._ends("ation"):
                self._r("ate")
            elif self._ends("ator"):
                self._r("ate")
        elif ch == 's':
            if self._ends("alism"):
                self._r("al")
            elif self._ends("iveness"):
                self._r("ive")
            elif self._ends("fulness"):
                self._r("ful")
            elif self._ends("ousness"):
                self._r("ous")
        elif ch == 't':
            if self._ends("aliti"):
                self._r("al")
            elif self._ends("iviti"):
                self._r("ive")
            elif self._ends("biliti"):
                self._r("ble")
        elif ch == 'g':
            if self._ends("logi"):
                self._r("log")

    def _step3(self) -> None:
        """Step 3 deals with -ic-, -full, -ness etc. similar to step 2."""
        ch = self.b[self.k]
        if ch == 'e':
            if self._ends("icate"):
                self._r("ic")
            elif self._ends("ative"):
                self._r("")
            elif self._ends("alize"):
                self._r("al")
        elif ch == 'i':
            if self._ends("iciti"):
                self._r("ic")
        elif ch == 'l':
            if self._ends("ical"):
                self._r("ic")
            elif self._ends("ful"):
                self._r("")
        elif ch == 's':
            if self._ends("ness"):
                self._r("")

    def _step4(self) -> None:
        """Step 4 takes off -ant, -ence etc., in context <c>vcvc<v>."""
        if self.k <= self.k0 + 1:
            return
        ch = self.b[self.k - 1]
        if ch == 'a':
            if not self._ends("al"):
                return
        elif ch == 'c':
            if not self._ends("ance") and not self._ends("ence"):
                return
        elif ch == 'e':
            if not self._ends("er"):
                return
        elif ch == 'i':
            if not self._ends("ic"):
                return
        elif ch == 'l':
            if not self._ends("able") and not self._ends("ible"):
                return
        elif ch == 'n':
            if not self._ends("ant") and not self._ends("ement") and not self._ends("ment") and not self._ends("ent"):
                return
        elif ch == 'o':
            if self._ends("ion") and self.j >= self.k0 and self.b[self.j] in ('s', 't'):
                pass
            elif not self._ends("ou"):
                return
        elif ch == 's':
            if not self._ends("ism"):
                return
        elif ch == 't':
            if not self._ends("ate") and not self._ends("iti"):
                return
        elif ch == 'u':
            if not self._ends("ous"):
                return
        elif ch == 'v':
            if not self._ends("ive"):
                return
        elif ch == 'z':
            if not self._ends("ize"):
                return
        else:
            return
        if self._measure() > 1:
            self.k = self.j

    def _step5(self) -> None:
        """Step 5 removes a final -e if m() > 1, and changes -ll to -l if m() > 1."""
        self.j = self.k
        if self.b[self.k] == 'e':
            a = self._measure()
            if a > 1 or (a == 1 and not self._cvc(self.k - 1)):
                self.k = self.k - 1
        if self.b[self.k] == 'l' and self._double_consonant(self.k) and self._measure() > 1:
            self.k = self.k - 1

    def stem(self, word: str) -> str:
        """Stem a word string with irregular verb lemmatization."""
        word = word.lower()
        word = IRREGULAR_LEMMAS.get(word, word)
        if len(word) <= 2:
            return word

        self.b = word
        self.k = len(word) - 1
        self.k0 = 0
        self._step1ab()
        self._step1c()
        self._step2()
        self._step3()
        self._step4()
        self._step5()
        return self.b[:self.k + 1]


@lru_cache(maxsize=32768)
def stem_word(word: str) -> str:
    """Bounded memoization, with no mutable stemmer shared across requests."""
    return PorterStemmer().stem(word)


def stem_words(words: List[str]) -> List[str]:
    """Stem a sequence of words."""
    return [stem_word(w) for w in words]
