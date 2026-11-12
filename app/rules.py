"""Standaardcategorieën en herkenningsregels.

Pas deze lijst gerust aan. Regels worden van boven naar beneden getoetst;
de eerste match wint. Een patroon is een reguliere expressie die wordt
toegepast op 'tegenpartij + omschrijving' (hoofdletterongevoelig).
Tip: gebruik \\b voor woordgrenzen, zodat 'HUUR' niet ook
'KOSTUUMVERHUUR' raakt.

Categorie-soorten:
  expense  = uitgave (telt mee in je uitgaven)
  income   = inkomsten
  transfer = geld verplaatsen (telt nergens mee: eigen rekeningen,
             creditcardaflossingen waarvan je de details al importeert,
             vermogensmutaties zoals beleggen of de verkoop van een huis)

Nieuwe categorieën in deze lijst verschijnen vanzelf na een herstart van
de app. Bestaande categorieën en je eigen aanpassingen blijven behouden.
"""

CATEGORIES = [
    # naam,                          soort,      kleur
    ("Wonen",                        "expense",  "#7c6f64"),
    ("Energie & water",              "expense",  "#d79921"),
    ("Telecom & internet",           "expense",  "#458588"),
    ("Verzekeringen",                "expense",  "#689d6a"),
    ("Zorg & apotheek",              "expense",  "#cc6666"),
    ("Leningen & studieschuld",      "expense",  "#8f3f71"),
    ("Belastingen & overheid",       "expense",  "#665c54"),
    ("Software & abonnementen",      "expense",  "#5b7fbf"),
    ("Streaming & media",            "expense",  "#b16286"),
    ("Boodschappen",                 "expense",  "#98971a"),
    ("Horeca & uit eten",            "expense",  "#d65d0e"),
    ("Auto, laden & parkeren",       "expense",  "#3c8a8a"),
    ("Openbaar vervoer",             "expense",  "#076678"),
    ("Reizen & vakantie",            "expense",  "#af3a03"),
    ("Winkelen",                     "expense",  "#9d7cd8"),
    ("Huis & tuin",                  "expense",  "#8a6f4e"),
    ("Persoonlijke verzorging",      "expense",  "#c9829d"),
    ("Sport & wellness",             "expense",  "#4f9d8a"),
    ("Huisdieren",                   "expense",  "#b5895a"),
    ("Cadeaus & attenties",          "expense",  "#e0a458"),
    ("Beroep & lidmaatschappen",     "expense",  "#5d6d9e"),
    ("Cultuur & uitjes",             "expense",  "#c47fa3"),
    ("Hobby & spellen",              "expense",  "#7a9e3b"),
    ("Loterijen & goede doelen",     "expense",  "#b8bb26"),
    ("Bank- & kaartkosten",          "expense",  "#928374"),
    ("Creditcard ICS (ongespecificeerd)", "expense", "#a89984"),
    ("Creditcard Amex (ongespecificeerd)", "expense", "#b3a58f"),
    ("Contant geld",                 "expense",  "#bdae93"),
    ("Betalingen aan personen",      "expense",  "#83a598"),
    ("Overig",                       "expense",  "#a0a0a0"),
    ("Salaris",                      "income",   "#2e8b57"),
    ("Schenkingen & giften",         "income",   "#4c9f70"),
    ("Terugbetalingen (Tikkie e.d.)", "income",  "#5fa86b"),
    ("Overige inkomsten",            "income",   "#79b87f"),
    ("Interne overboeking",          "transfer", "#b0b0b0"),
    ("Creditcard aflossing",         "transfer", "#c0c0c0"),
    ("Vermogen & beleggen",          "transfer", "#9aa5b1"),
    ("Aflossing hypotheek",          "transfer", "#8fa3b8"),
]

# Oude categorienamen die bij het opstarten worden omgezet (ook in je eigen
# aanpassingen).
RENAMES = {"Kinderen & school": "Cadeaus & attenties"}

# Categorieën die nooit meetellen in overzicht en gemiddelden (eenmalige
# meevallers). Ze blijven zichtbaar bij Transacties.
EXCLUDE_FROM_AVERAGES = {"Schenkingen & giften"}

# (patroon, categorie, opties)
# opties: source = 'bank'|'amex', sign = 'in'|'out'
RULES = [
    # --- overboekingen, aflossingen, vermogen
    (r"SPAARREKENING|SENT FROM N26", "Interne overboeking", {}),
    # Evi-beleggingsrekening: stortingen via iDEAL aan 'Van Lanschot N.V.' en
    # onttrekkingen 'Van Lanschot Kempen inzake EVI'
    (r"INZAKE EVI|EVIREKENING|^VAN LANSCHOT N\.V\.|DERDENGELDEN .*NOTARIS|NOTARIS.*DERDENGELDEN|BELEGGERSGIRO|BELEGGINGSREKENING", "Vermogen & beleggen", {}),
    (r"OPEN BANK", "Leningen & studieschuld", {"sign": "out"}),
    (r"AMERICAN EXPRESS|\bAMEX\b", "Creditcard aflossing", {"source": "bank"}),
    (r"HARTELIJK BEDANKT VOOR UW BETALING|BETALING ONTVANGEN|UW BETALING", "Creditcard aflossing", {"source": "amex"}),
    (r"INTERNATIONAL CARD SERVICES|INT CARD SERVICES|ICS CARDS|\bICS\b", "Creditcard ICS (ongespecificeerd)", {"source": "bank", "sign": "out"}),

    # --- inkomsten
    (r"SALARIS|\bLOON\b", "Salaris", {"sign": "in"}),
    (r"TIKKIE|BETAALVERZOEK|WIEBETAALTWAT|RESERVERING", "Terugbetalingen (Tikkie e.d.)", {"sign": "in"}),

    # --- specifieke uitzonderingen die anders door een bredere regel worden gepakt
    (r"KOSTUUMVERHUUR", "Winkelen", {}),
    (r"MAXI ZOO|DIERENKLINIEK|KATTENKLINIEK|DIERENARTS|DIERENSPECIAAL|ZOOPLUS|PETS PLACE|\bDIERENLOT\b", "Huisdieren", {}),
    (r"FITNESS|WEFITNESS|BASIC.FIT|SPORTSCHOOL|SAUNA|THERMEN|BAD NIEUWESCHANS|WELLNESS|ZWEMBAD|YOGA|PADEL|TENNIS|GOLF", "Sport & wellness", {}),
    (r"SMYTHS|INTERTOYS|BART SMIT|GREETZ|TOPBLOEMEN|TOPGESCHENKEN|BLOEMEN|BLOEMIST|FLEUROP|KAARTJE2GO|CADEAU|\bKADO\b", "Cadeaus & attenties", {"sign": "out"}),
    (r"SPROOKJESHOF", "Cultuur & uitjes", {}),
    (r"\bONVZ\b|VVAA SCHADE", "Verzekeringen", {}),
    (r"GAMEFOUND|KICKSTARTER|BOARDGAMEARENA|999 GAMES|MANTICGAMES|SPELLENWINKEL|BORDSPEL|PEAKDESIGN|PEAK DESIGN|KASE FILTERS|VERREKIJKER|CAMERANU|KAMERA EXPRESS", "Hobby & spellen", {"sign": "out"}),
    (r"EUROPEAN SOCIETY|NEDERLANDSE VERE\b|ANESTHESIOLOGIE|ANESTHE|VVAA(?! SCHADE)|VEREN?IGING VVAA|MEDISCHE GESCHIEDENIS|\bCNV\b|\bFNV\b|\bKNMG\b|\bLAD\b|KURSUSPORTALEN|CONGRES|BIG-REGISTER|GENOOTSCHAP|MYSCRUBS", "Beroep & lidmaatschappen", {"sign": "out"}),
    (r"WERELDPAS|BANKKOSTEN|KOSTEN BETAALPAKKET|KAARTLIDMAATSCHAPSBIJDRAGE|BIJDRAGE EXTRA KAART|JAARLIJKSE BIJDRAGE", "Bank- & kaartkosten", {}),

    # --- betalingsverzoeken aan personen (niet zakelijk)
    (r"(TIKKIE|BETAALVERZOEK).*\b(DINER|DINNER|ETEN|ETENTJE|LUNCH|BORREL|FRIET|FRIETTENT|BBQ|PIZZA|SUSHI|DRANKJES|BIER)\b", "Horeca & uit eten", {"sign": "out"}),
    (r"(TIKKIE|BETAALVERZOEK).*\b(PROMOTIE|AFSCHEID|VERJAARDAG|JUBILEUM|BRUILOFT|GEBOORTE|PENSIOEN|GESCHENK)\b", "Cadeaus & attenties", {"sign": "out"}),
    (r"VIA TIKKIE(?! ZAKELIJK)|(?<!ZAKELIJK )BETAALVERZOEK", "Betalingen aan personen", {"sign": "out"}),

    # --- vaste lasten
    (r"HYPOTHE|VVE |VERENIGING VAN EIGENAARS|\bHUUR\b|HUURPENNING|WONINGCORPORATIE|SERVICEKOSTEN|VERHUIZING|JAN DE JONG VERHUIZ", "Wonen", {}),
    (r"ENECO|VATTENFALL|ESSENT|GREENCHOICE|BUDGET ENERGIE|ENERGIEDIRECT|FRANK ENERGIE|TIBBER|VAANSTER|THREEFORCE|WATERBEDRIJF|VITENS|WATERLEIDING|\bWMD\b|EVIDES|\bPWN\b|OASEN", "Energie & water", {}),
    (r"VODAFONE|ZIGGO|\bKPN\b|T-MOBILE|ODIDO|TELE2|SIMYO|BEN NEDERLAND|YOUFONE|DELTA FIBER|CAIWAY|FREEDOM INTERNET", "Telecom & internet", {}),
    (r"VERZEKER|TAF BV|\bONVZ\b|BALOISE|CENTRAAL BEHEER|NATIONALE.NEDERLANDEN|\bASR\b|ACHMEA|INTERPOLIS|OHRA|UNIVE|FBTO|ZILVEREN KRUIS|MENZIS|CZ GROEP|CZ ZORG|\bVGZ\b|\bDSW\b|ALLIANZ|AEGON|MOTORVOERTUIGEN", "Verzekeringen", {}),
    (r"APOTHEEK|HUISARTS|TANDARTS|FYSIO|ZIEKENHUIS|OPTICIEN|HANS ANDERS|PEARLE|SPECSAVERS|LENSPLAZA|VISION DIRECT|LENSON|PHARMA|MDT X-RAY|HIELSPOOR", "Zorg & apotheek", {}),
    (r"\bDUO\b|STUDIESCHULD|\bLENING\b|KREDIET|FINANCIERING|SANTANDER CONSUMER", "Leningen & studieschuld", {}),
    (r"SCHENKING|GEFELICITEERD MET JE VERJAARDAG|PRETTIGE FEESTDAGEN", "Schenkingen & giften", {"sign": "in"}),
    (r"BELASTINGDIENST.*\b(?=[A-Z0-9-]*[A-Z])[A-Z0-9]{1,3}-[A-Z0-9]{2,3}-[A-Z0-9]{1,3}\b|MOTORRIJTUIGENBELASTING", "Auto, laden & parkeren", {"sign": "out"}),
    (r"BELASTINGDIENST|TERUGGAAF", "Overige inkomsten", {"sign": "in"}),
    (r"BELASTINGDIENST|BELASTINGKANT|BELASTINGKANTOOR|BELASTINGSAMENWERKING|LOKALE BELASTINGEN|GEMEENTE|GEM\. |WATERSCHAP|NOORDERZIJLVEST|HUNZE EN AAS|\bCJIB\b|KADASTER|MINISTERIE|\bRDW\b|\bBSGR\b|NOORDENBELASTING", "Belastingen & overheid", {}),

    # --- digitale abonnementen en media
    (r"CLAUDE\.AI|ELEVENLABS|\bSUNO\b|HOSTHAVOC|\bTRMNL\b|SOVERIN|MVOS WEBDESIGN|ANTHROPIC|OPENAI|CHATGPT|1PASSWORD|BACKBLAZE|TODOIST|READCUBE|SIGNAL FOUNDATION|CAPTIVATE|MIJNDOMEIN|CLOUDFLARE|GITHUB|DROPBOX|MICROSOFT|GOOGLE|NOTION|ADOBE|\bSPARK\b|READDLE|SYNOLOGY|CULTUREDCODE|SETAPP|ICLOUD|MONEYBIRD", "Software & abonnementen", {}),
    (r"AMZN DIGITAL|NETFLIX|HBOMAX|HBO MAX|DISNEY|SPOTIFY|NLZIET|VIDEOLAND|KINDLE|AUDIBLE|WUXIAWORLD|AMZNPRIME|PRIME VIDEO|YOUTUBE|APPLE\.COM/BILL|STORYTEL|\bNRC\b|VOLKSKRANT|DAGBLAD|TROUW|DE CORRESPONDENT|DPG MEDIA|MEDIAHUIS|PLEX|TRAKT|NINTENDO|PLAYSTATION|STEAM", "Streaming & media", {}),

    # --- reizen (voor horeca/overheid, zodat hotels niet elders belanden)
    (r"\bKLM\b|TRANSAVIA|RYANAIR|EASYJET|LUFTHANSA|AIRLINE|AIRPORT|AIRSIDE|MAYFAIR JET|\bAIR\b|AIRWAYS|AIRLINES|AIRLINK|DERTOUR|MELIA|MELIÁ|EUROSTAR|12GO|\bUKVI\b|AIRALO|MAGLEV|BANYAN|WINE TRAM|BOOKING\.COM|AIRBNB|HOTEL|RADISSON|HILTON|MARRIOTT|\bIBIS\b|HERTZ|\bAVIS\b|EUROPCAR|\bSIXT\b|BIDVEST|CAR RENTAL|RIKSJA|SCHIPHOL|GUARANT|LANDAL|CENTER PARCS|SUNWEB|SUMMIT TRAVEL|TUI |CORENDON|WAGENBORG|DOEKSEN|TESO|M\.S\.ROTTUM|LODGE|SAFARI|DIVERS|TRAVELLE|FUNIVIA|FUNBOOKER|VAKANTIE|CAMPING|SANPARKS|\bKNP\b|BALI|WWW\.DUS\.COM|SHINGWEDZI|GAME RES", "Reizen & vakantie", {}),

    # --- horeca (voor boodschappen: 'pizzabakker' is geen bakker)
    (r"CAFE|CAFÉ|RESTAURANT|RESTAUTANT|HEERLIJKHEID|VALK WESTERBROEK|VERMAAT|\bREST\. |STARBUCKS|MC ?DONALD|BURGER|THUISBEZORGD|TAKEAWAY|UBER ?EATS|DELIVEROO|PIZZA|SUSHI|BISTRO|BRASSERIE|LUNCH|VENDING|STADSCAFE|\bBAR\b|TAPAS|BODEGA|EATHAI|\bPHO\b|FUSION|AFGHAANS|NEW SIN GUANG|HANA SATO|BOEDDHA|DRIE GEZUSTERS|PIECE OF CAKE|MUCHO MAS|PACHAMAMA|BETERE TIJDEN|FOUR ROSE|\bAMARI\b|BRAKZAND|EPICO|HANZEBORG|FRIETTENT|SNACKBAR|IJSSALON|RINCON|MADRE AMIGA|MISULU|PAKHUUS|GRAND CAFE|EETCAFE|KEBAB|SHOARMA|WOK|HERBERG|DOMINO|SITEDISH|HMSHOST|SOEPBOER|NIEUWE KOLK|VILLA OLIVIA|STRAND TIEN|PAVILJOEN|TEROEMBOE|KITCHEN|RISTORANTE|\bREST A\b|EETWINKEL|MOFONGO|DON PABLO|TREKPLEISTER|PRET A MANGER|GASTRONO", "Horeca & uit eten", {}),

    # --- dagelijks
    (r"MARLEY ?SPOON|HELLOFRESH|GRUTTO|ALBERT HEIJN|\bAH\b|JUMBO|LIDL|ALDI|\bPLUS\b|\bDIRK\b|DEKAMARKT|\bCOOP\b|\bSPAR\b|PICNIC|EKOPLAZA|VOMAR|HOOGVLIET|MARQT|CRISP|KAUFLAND|HANOS|MAKRO|VERSHAL|BAKKERIJ|\bBAKKER\b|SLAGER|KAASHANDEL|GROENTEBOER|MARKET|MERCADO|CHAMPAGNE|\bCHAMP |WIJNHANDEL|GALL & GALL|SLIJTERIJ", "Boodschappen", {}),
    (r"PLUGSURFING|SHELL RECHARGE|SHELL EV|FASTNED|IONITY|ALLEGO|VATTENFALL INCHARGE|TESLA|POLESTAR|CARSUB|BROEKHUIS|\bESSO\b|\bSHELL\b|\bBP\b|\bTOTAL\b|\bTINQ\b|\bTANGO\b|Q-PARK|PARKEER|PARKING|PARKMOBILE|YELLOWBRICK|EASYPARK|INTERPARKING|APCOA|\bANWB\b|KWIK.FIT|GARAGE|WASSTRAAT|AANHANGWAGEN|BANDEN|CARWASH|\bEV\d{3,5}\b|\bENI\b|ENGEN|AUTO PARCS", "Auto, laden & parkeren", {}),
    (r"OVPAY|NS GROEP|NS REIZIGERS|\bNS\b|ARRIVA|QBUZZ|KEOLIS|CONNEXXION|\bGVB\b|\bRET\b|\bHTM\b|METRO|OV-CHIPKAART|TRANSLINK|UBER(?! ?EATS)|\bUBR\b|\bBOLT\b|TAXI|\bTFL\b", "Openbaar vervoer", {}),
    (r"FEVER\*|TABLAO|FLAMENCO|PALACIO REAL|MUSEUM|MUSEO|MUSEE|THEATER|THEATRE|THEATR|TICKETING|ZOOPARC|DIERENPARK|PHANTASIALAND|EFTELING|PRETPARK|LASER GAME|VILLA ROMANA|NOORDERZON|SCHOUWBURG|BIOSCOOP|PATHE|KINEPOLIS|\bVUE\b|CONCERT|TICKETMASTER|TICKETCOUNTER|WEEZEVENT|SPOT GRONINGEN|DE MARKIES|PRINSENHOF|OCEARIUM|JARDIN|DIERENTUIN|\bZOO\b|BOULDERS|PUERTA DE|RIJKSMUSEUM|ZUMMERB|FESTIVAL|ESCAPE", "Cultuur & uitjes", {}),
    (r"STAATSLOTERIJ|POSTCODE LOTERIJ|LOTERIJ ORGANISATIE|NEDERLANDSE LOTERIJ|LOTTO|VRIENDENLOTERIJ|GROTE CLUBACTIE|GOEDE DOEL|\bKWF\b|UNICEF|RODE KRUIS|ARTSEN ZONDER|GREENPEACE|\bWNF\b|NATUURMONUMENTEN|SPOEDEISENDE HULP BIJ KIN|AMNESTY|HARTSTICHTING|KINDERPOSTZEGELS", "Loterijen & goede doelen", {}),
    (r"GELDAUTOMAAT|GELDMAAT|\bGEA\b|\bATM\b|GELDOPNAME", "Contant geld", {}),
    (r"BAUHAUS|VENTILATIE|INTRATUIN|TUINWERELD|PLANTJES|PRATESI|TUINCENTRUM|GROENOVATIE|GREENOVATION|GROENE REGIO|KWANTUM|\bJYSK\b|HOME24|LOODS 5|LEENBAKKER|IKEA|GAMMA|PRAXIS|KARWEI|HORNBACH|HUBO|KAMPHUIS KOOK|DELOOX|ZUIVER|LINNEN|KUNSTINLIJST|SCHILDERWERK|BEVER|FLINDERS|FONQ|WOONWINKEL", "Huis & tuin", {}),
    (r"BOLDKING|BARBERSHOP|BARBIER|KAPSALON|KAPPER|VISAGIE|HAIR|NAGELSTUDIO|SCHOONHEID|DM-DROGERIE|\bDM\b|KRUIDVAT|\bETOS\b|DOUGLAS|RITUALS|PARFUM|PERFUMERIA|EASYCOSMETIC|LUSH|\bBOOTS\b|SEPHORA", "Persoonlijke verzorging", {}),
    (r"APPLE\.COM/(?!BILL)|WEFASHION|DARN TOUGH|ON CLOUD|\bETSY\b|ALLSAFE|EUROHELL|ONLINEWINKEL|CLOUD STORE|\bINVZI\b|SUUNTO|ACTION|HEMA|BOL\.COM|BOLCOM|COOLBLUE|AMAZON|TEMU|WEHKAMP|ZALANDO|OTTO B\.?V|\bOTTO\b|ADIDAS|NIKE|DECATHLON|\bSCORE\b|WE FASHION|HILFIGER|DEDOLES|MEDIA MARKT|APPLE STORE|CAMERANU|KOOISTRA|BLOKKER|XENOS|PRIMARK|H&M|UNIQLO|BOEKHANDEL|BRUNA|TOPBLOEMEN|TOPGESCHENKEN|BLOEMEN|FRITZSHOP|PROWIN|JAMEY FITZ|SURFSPOT|FIETS|BIKE|GREETZ|KAMERA EXPRESS|PLUTO SPORT|SPELLENWINKEL|BUDGETTROPHY|APPLE\.COM NL|\bCIGO\b|PRIMERA", "Winkelen", {}),
    # vangnet: overige stichtingen zijn meestal goede doelen (maar niet
    # betaaldienstverleners zoals 'Stichting Mollie Payments')
    (r"STICHTING (?!MOLLIE|DERDENGELDEN|PAY|BELEGGERS|KOSTUUM)", "Loterijen & goede doelen", {"sign": "out"}),
]
