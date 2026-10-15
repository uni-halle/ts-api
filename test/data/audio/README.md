# Test audio

Short clips for the tests with a real Whisper model (`test/TestRealModel.py`).
Both are re-encoded to 16 kHz mono Opus to keep them small.

## jfk_inaugural_1961_en.ogg

- Content: excerpt of the inaugural address of John F. Kennedy, 20 January 1961
  ("And so, my fellow Americans, ask not what your country can do for you;
  ask what you can do for your country.").
- License: public domain. The speech was given by the President of the United
  States in his official capacity and is a work of the US federal government,
  which is not protected by copyright (17 U.S.C. § 105).
- Source: `tests/jfk.flac` of the openai/whisper repository,
  <https://github.com/openai/whisper/blob/main/tests/jfk.flac>
  (SHA-256 `63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715`).
- Converted with
  `ffmpeg -i jfk.flac -ac 1 -ar 16000 -c:a libopus -b:a 24k jfk_inaugural_1961_en.ogg`.

## goethe_grimm_espeak_de.ogg

- Content: synthetic speech (eSpeak NG 1.51, voice `de`) of two public domain
  texts: "Wandrers Nachtlied" by Johann Wolfgang von Goethe (died 1832) and
  the beginning of "Die Sterntaler" by the Brothers Grimm (died 1859/1863).
- Generated with

      espeak-ng -v de -s 150 -w de.wav "Über allen Gipfeln ist Ruh, in allen Wipfeln spürest du kaum einen Hauch. Die Vögelein schweigen im Walde. Warte nur, balde ruhest du auch. Es war einmal ein kleines Mädchen, dem war Vater und Mutter gestorben, und es war so arm, dass es kein Kämmerchen mehr hatte, darin zu wohnen, und kein Bettchen mehr, darin zu schlafen."
      ffmpeg -i de.wav -ac 1 -ar 16000 -c:a libopus -b:a 24k goethe_grimm_espeak_de.ogg
