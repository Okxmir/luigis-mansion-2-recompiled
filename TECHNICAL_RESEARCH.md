# Recherche technique

## Cartouche locale

| Champ | Observation |
| --- | --- |
| Conteneur | NCSD de 1 073 741 824 octets |
| SHA-256 | `EB4E7193904F704D1984F9F6DFDB14D32629DADA12EB43B8A4E3DE29FF8F87ED` |
| Identification | `CTR-P-AGGP`, Title ID `0004000000076500`, titre ExHeader `LM3DS` |
| Région | Masque SMDH `0xC` et produit européen |
| Révision | Champ remaster de l’ExHeader à 0. Version du format NCCH à 2 |
| Partitions | 0 application, 1 manuel, 2 distribution locale, 7 mise à jour système |
| SDK | `CTR_SDK-4_2_3_200_none`, firmware `02_35_00`, NEX `3_1_0` |

Le produit européen est confirmé par le manuel de Nintendo. Le numéro NCCH décrit le format du conteneur. [Manuel électronique officiel](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/nintendo_3ds_2/luigi_s_mansion_1/ElectronicManual_Nintendo3DS_LuigisMansion2_ES.pdf)

La partition principale commence à `0x4000` et compte 850 268 160 octets. Elle utilise le schéma NCCH v2 AES-CTR d’origine, avec le slot retail `0x2C`, sans méthode secondaire et sans seed. La conversion locale ouvre la cartouche en lecture seule et écrit une partition CXI séparée. La clé n’est pas stockée par le projet. Les trois empreintes NCCH, les quatre fichiers ExeFS et les 206 276 blocs de l’arbre IVFC ont été vérifiés. Les signatures RSA et le contenu des partitions 1 et 2 restent hors de cette vérification. La partition 7 a été déchiffrée temporairement en mémoire pour vérifier l’empreinte de son en-tête RomFS et chercher la police système occidentale. Son inventaire de 60 fichiers ne contient pas le titre `0004009b00010202`. [Implémentation Project CTR](https://github.com/3DSGuy/Project_CTR/tree/master/ctrtool), [paramètres de la variante NCCH v2](https://github.com/aszuraz/3DS-Decrypt/blob/main/decrypt_3ds.py)

Le fichier `.code` de 4 908 592 octets utilise la compression LZSS inversée. Après décompression, `code.bin` mesure 8 716 288 octets et son SHA-256 vaut `FEEAA71350C2712C5402FBEEFA9BE4AAED0A77442DF43AF0C14326B2524CA2C8`.

| Segment | Adresse | Taille utile |
| --- | ---: | ---: |
| .text | `0x00100000` | `0x799BE8` |
| .rodata | `0x0089A000` | `0x05EED0` |
| .data | `0x008F9000` | `0x056108` |
| .bss | `0x0094F108` | `0x062AFC` |

Le RomFS a livré 1 878 fichiers, dont 755 paires `.dict` et `.data`. Les dictionnaires commencent tous par les mêmes quatre octets `58 24 F3 A9`. Plusieurs flux `.data` commencent par un en-tête zlib. Les 338 banques audio commencent par `BKHD` et le paquet `art/wwiseaudio/streamedfiles.pck` par `AKPK`. Ces signatures et le dossier indiquent une chaîne audio Wwise. Aucun fichier CRO, CRS ou CRR n’a été trouvé. Le traitement des animations, des scènes et des données internes aux archives reste à valider. [Travaux LM2L sur les formats de ressources](https://github.com/hadashisora/LM2L)

## Traduction et services natifs

- L’ARM11 MPCore implémente ARMv6K. La traduction doit suivre les changements de mode ARM et Thumb, les indicateurs de condition, les registres VFP et les accès mémoire en little-endian. Les adresses originales restent des offsets 32 bits. Le runtime réserve l’espace virtuel correspondant et ne valide que les plages nécessaires. [Manuel ARM11 MPCore](https://documentation-service.arm.com/static/5e8e1e0388295d1e18d368b2)
- Le chemin retenu utilise l’émetteur ARM et Thumb vers C de Clockwork à la révision `3047d9e990be4ac2c84174cb570dfec569c882e9`. MSVC compile le C en x64. Les appels indirects utilisent la table de fonctions compilées. Une cible absente produit un diagnostic. Le projet réutilise les services Windows et la présentation SDL3 de Clockwork et compile un exécutable dédié à LM2. Les points d’entrée, appels système et protocoles du jeu doivent être validés séparément. La révision utilisée inclut une licence MIT. [Clockwork et sa licence](https://github.com/watchmakerers/clockwork), [architecture de Clockwork](https://github.com/watchmakerers/clockwork/blob/master/docs/ARCHITECTURE.md)
- Le passage par LLVM IR permettrait d’exprimer les opérations ARM en SSA et d’utiliser le backend x64. Il faudrait encore traduire les modes ARM et Thumb, les drapeaux et le flot de contrôle. L’émetteur C permet de vérifier ces mêmes éléments avec une chaîne testée. [Référence LLVM IR](https://llvm.org/docs/LangRef.html)
- Capstone 5.0.9 est présent et a servi à comparer le désassemblage du démarrage. Ghidra et son p-code, RetDec et l’IL de Binary Ninja sont des outils d’analyse ou de lifting. LIEF aide à inspecter des conteneurs comme ELF et PE. Le fichier extrait ici est une image plate dont l’ExHeader fournit la carte mémoire. Ces outils ne sont pas requis pour compiler le portage. [Capstone](https://github.com/capstone-engine/capstone), [Ghidra p-code](https://ghidra.re/ghidra_docs/languages/html/pcoderef.html), [RetDec](https://github.com/avast/retdec), [Binary Ninja IL](https://docs.binary.ninja/dev/bnil-overview.html), [LIEF](https://github.com/lief-project/LIEF)
- Les travaux de TriAevum sur Ocarina of Time 3D et MM3D-PC démontrent l’approche AOT et Vulkan sur d’autres titres. TriAevum est GPL-3.0 et comporte un module tiers avec des droits propres. `fearkov/3dsrecomp` est couplé à Zakuro avec un repli vers son interpréteur. Les travaux du Luigi’s Mansion GameCube portent sur une autre architecture. Aucune source de ces projets n’a été importée. [TriAevum](https://github.com/coccofresco/TriAevum), [MM3D-PC](https://github.com/Volpe34/MM3D-PC), [3dsrecomp](https://github.com/fearkov/3dsrecomp), [Luigi’s Mansion GameCube](https://github.com/ThePlayerRolo/lm-decomp)
- La recherche LM2_SaveEditor situe le contrôle des sauvegardes à `0x003B4B98` sur l’édition européenne. Le désassemblage local retrouve une routine de 61 instructions à cette adresse. Le test natif recalcule le CRC avec le polynôme réfléchi `0xEDB88320`, sans utiliser la table du jeu dans la référence. LM2_SaveEditor et LM2L servent de références documentaires sans réutilisation de leur code. [Analyse de la sauvegarde LM2](https://github.com/TollyH/LM2_SaveEditor#crc-checksums), [LM2L](https://github.com/hadashisora/LM2L)

## Premiers écarts de démarrage

L’original attend à `0x0010B08C` que le bit 0 de `0x1FF81086` soit positionné avant de lire l’identité matérielle. Le runtime initialise désormais cet indicateur après avoir écrit l’identité de la console retail. [Carte mémoire de configuration observée](https://3dbrew.org/wiki/Configuration_Memory#Shared_Memory_Page_For_ARM11_Processes)

À `0x005277D4`, le mot ARM `0xB1200A76` a un champ de condition LT. Le moteur d’analyse de Clockwork traitait toutes les instructions de ce type comme des terminaisons inconditionnelles. Le correctif conserve la suite du flot quand la condition échoue. Le générateur conserve le diagnostic de trappe si la condition passe.

Le jeu appelle `dlp:SRVR IsChild` pendant le démarrage. Le service local répond que la cartouche ne participe à aucune distribution en cours. Il traite cette requête uniquement. [Protocole Download Play](https://www.3dbrew.org/wiki/DLP_Services)

Le jeu demande ensuite `APT:GetSharedFont`. Le runtime charge un BCFNT local, relocalise les pointeurs et expose le bloc en mémoire linéaire pour permettre au GPU d’accéder aux atlas de glyphes. La police compatible est construite avec un générateur GPLv2 utilisé comme outil externe. Le runtime ne lie aucun code de ce générateur. [Format du bloc de police dans libctru](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/font.h), [générateur et licence](https://github.com/B3n30/citra_system_archives/tree/f470e0c9d341db73b8a24880295d2eab4cd81660)

LM2 transfère l’image de l’écran supérieur par des tampons intermédiaires de 256 × 416 et 128 × 416. Le chemin rapide Vulkan supposait qu’un transfert RGB vers un tampon linéaire aboutissait directement à l’écran. Dans ce cas, il laissait la mémoire originale inchangée alors que les commandes `TextureCopy` suivantes la relisaient. Le correctif limite ce chemin aux dimensions LCD et fait passer les transferts intermédiaires par la mémoire du jeu.

Le jeu a demandé une archive de sauvegarde de `0x40000` octets, avec 0 répertoire, 3 fichiers et duplication activée. Une réponse avec des métadonnées par défaut déclenchait un reformatage. Le runtime conserve maintenant la demande du jeu, importe les métadonnées des profils locaux existants et sauvegarde les données avant écriture ou reformatage. [FormatSaveData](https://www.3dbrew.org/wiki/FS%3AFormatSaveData), [GetFormatInfo](https://www.3dbrew.org/wiki/FS%3AGetFormatInfo)

Lors de l’arrivée au manoir dans A-1, `BLX r12` à `0x006650B4` a appelé une routine d’interpolation VFP absente de la table des fonctions compilées. Le constructeur écrit dans une table en BSS le pointeur vers `0x008D1710`, qui contient l’adresse ARM `0x0084B1D4`. Le traducteur utilise désormais ce pointeur comme entrée vérifiée. Les deux autres cibles de cette table étaient déjà compilées.
