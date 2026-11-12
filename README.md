# NHL-otteluiden tulokset ja analyysi

Suomenkielinen Python-komentorivisovellus hakee NHL-ottelut julkisesta rajapinnasta, tallentaa ne paikallisesti ja näyttää tulosanalyysin. API-avainta tai ulkoisia Python-kirjastoja ei tarvita. Vaatimus: Python 3.10 tai uudempi.

## Käyttö

Avaa pääte projektikansiossa ja suorita:

```powershell
py nhl.py --start 2025-01-01 --end 2025-01-07
```

Yksi päivä ja CSV-tallennus:

```powershell
py nhl.py --start 2025-01-01 --output data/ottelut.csv
```

Ilman valintoja `py nhl.py` hakee tietokoneen paikallisen kalenterin eilisen päivän. Jos käytössäsi on `python`-komento, voit käyttää sitä `py`-komennon sijaan. `py nhl.py --help` näyttää ohjeen.

Tässä työympäristössä `py` ei löytänyt Python-asennusta. Sovellus testattiin LibreOfficen Python 3.12:lla, jolla sen voi käynnistää PowerShellissä näin:

```powershell
& 'C:\Program Files\LibreOffice\program\python.exe' nhl.py --start 2025-01-01 --end 2025-01-02
```

`--start` ja `--end` ovat NHL:n ottelupäiviä muodossa VVVV-KK-PP. Molemmat rajapäivät sisältyvät hakuun. Ilman loppupäivää haetaan vain alkupäivä. Yhdellä ajolla voi hakea enintään 366 päivää; jokaisesta päivästä tehdään yksi pyyntö, jonka aikakatkaisu on 30 sekuntia. NHL:n ottelupäivä voi poiketa Suomen kalenteripäivästä. Aloitusajat tallennetaan UTC-aikoina.

## Tallennus

Oletustiedosto on `data/nhl_ALKUPÄIVÄ_LOPPUPÄIVÄ.json`. `--output` valitsee tiedoston ja sen pääte (`.json` tai `.csv`) tallennusmuodon. Hakemistot luodaan tarvittaessa. **Samanniminen tiedosto korvataan.**

Molempiin muotoihin tallennetaan ottelun tunniste, ottelupäivä, aloitusaika, joukkueiden lyhenteet, maalit, tila ja ratkaisutapa. JSON sisältää lisäksi lähteen, hakuajan ja päivämäärävälin. Puuttuvat arvot ovat JSONissa `null` ja CSV:ssä tyhjiä. Myös tulevat ja keskeneräiset ottelut tallennetaan. Tyhjältä päivältä tallennetaan tyhjä ottelulista tai CSV-otsikkorivi.

## Tunnusluvut ja analyysi

Ohjelma näyttää ottelulistan sekä seuraavat tunnusluvut:

- Päättyneiden otteluiden määrä ja maalien kokonaismäärä.
- Maalien keskiarvo ottelua kohti.
- Kotivoittojen prosenttiosuus.
- Keskimääräinen absoluuttinen maaliero.
- Jatkoajalle tai voittolaukauksiin menneiden otteluiden prosenttiosuus.

Analyysi kertoo, voittivatko koti- vai vierasjoukkueet useammin, ja listaa runsasmaalisimmat ottelut, myös tasatulokset niiden välillä. Laskenta huomioi vain tilat `FINAL` ja `OFF`. Kesken olevat ottelut eivät vääristä tunnuslukuja. Jos päättyneitä otteluita ei ole, ohjelma kertoo, ettei analyysiä voida laskea. Jatkoaikaosuuden nimittäjä sisältää vain ottelut, joiden ratkaisutapa tunnetaan (`REG`, `OT`, `SO`).

Maalit ovat tulostaulun maaleja, joten voittolaukauskilpailun ratkaisumaali sisältyy tulokseen. Kotivoitto tarkoittaa API:n kotijoukkueeksi merkitsemän joukkueen voittoa myös neutraalilla kentällä. Analyysi kuvaa valittua aineistoa eikä osoita tilastollista kotietua tai ennusta tulevia otteluita.

## Rajapinta ja virhetilanteet

Lähde: [NHL:n julkinen tulosrajapinta, esimerkkipäivä](https://api-web.nhle.com/v1/score/2025-01-01). Sovellus käyttää osoitetta `https://api-web.nhle.com/v1/score/VVVV-KK-PP`. Ulkoisen rajapinnan saatavuus ja rakenne voivat muuttua.

Verkkovirhe, aikakatkaisu tai virheellinen vastaus keskeyttää haun virheilmoitukseen ja paluuarvoon 1. Osittaista hakutulosta ei tallenneta. Virheelliset komentorivivalinnat tuottavat ohjeen ja paluuarvon 2. Onnistunut ajo palauttaa 0.

## Testit

```powershell
py -m unittest -v
```

Testit eivät tarvitse verkkoyhteyttä. Ne tarkistavat tunnusluvut, keskeneräisten otteluiden poissulkemisen, tyhjän aineiston, puuttuvat ratkaisutavat, JSON/CSV-tallennuksen, päivävälin haun ja virhetilanteet.
