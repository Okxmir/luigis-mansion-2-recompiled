# Construction Windows x64

Il faut Windows x64, Visual Studio avec la charge de travail **Développement Desktop en C++**, le SDK Windows, CMake et Ninja, ainsi que Python 3.11 ou ultérieur sur le PATH. La préparation télécharge et vérifie les dépendances de construction dans `build/upstream`.

Utilise une image de ta cartouche européenne `CTR-P-AGGP` correspondant à la révision prise en charge par le projet. Conserve l’image de la cartouche et le fichier de clé hors du dépôt. Dans PowerShell, ouvre le dossier du dépôt, adapte les deux chemins de l’exemple, puis exécute les commandes dans l’ordre.

```powershell
python -m pip install cryptography Pillow
.\scripts\prepare.ps1 -Cartridge "C:\Jeux\LM2-EUR.3ds" -KeyFile "C:\Prive\slot0x2c.key" -CodeOnly -WithGpuShaders
.\scripts\prepare_font.ps1
.\scripts\build_release.ps1
.\scripts\run_tests.ps1
.\scripts\package.ps1
```

`prepare.ps1` réutilise `extracted/LM2-EUR.cxi` quand cette partition locale existe. Si tu disposes déjà d’une partition compatible déchiffrée, place-la à cet emplacement et lance `.\scripts\prepare.ps1 -CodeOnly -WithGpuShaders`. Cette voie ne nécessite que Pillow pour la génération de la police.

Pour une cartouche chiffrée, `-KeyFile` désigne un fichier texte local qui contient les 32 chiffres hexadécimaux de la clé du slot retail `0x2C`. La variable d’environnement `LGM2_KEYX_2C` est aussi acceptée. `-CodeOnly` vérifie le RomFS et évite d’en extraire chaque fichier sur le disque. Le jeu lit le RomFS directement dans la partition CXI.

Pour Debug, lancer `scripts/build_debug.ps1`, puis `scripts/run_tests.ps1 -Configuration Debug`. Le premier build des sources générées est volumineux. Le mode `LGM2_FAST_BUILD` accélère les itérations en compilant ces sources sans optimisation.

Le jeu demande une police système BCFNT au démarrage. `prepare_font.ps1` génère localement une police compatible à partir des ressources du projet [System Files Generator](https://github.com/B3n30/citra_system_archives). Ce script utilise Pillow. Le chargement accepte également un BCFNT little-endian non relocalisé fourni localement. Le placer à côté de l’exécutable sous le nom `shared-font.bcfnt` ou indiquer son chemin avec `LGM2_SHARED_FONT`.

Les essais du point d’entrée peuvent être bornés dans le temps et consignés.

```powershell
python tools/boot_probe.py --seconds 15 --log boot-probe.txt
python tools/boot_probe.py --graphics --seconds 15 --log boot-graphics.txt
```

Le programme cherche `LM2-EUR.cxi` à côté de l’exécutable puis dans `../extracted`. Un argument permet de fournir le chemin explicitement. Le programme valide la version de code avant de lancer la traduction correspondante. Le dossier `userdata` est local à l’exécutable, sauf si `LGM2_DATA_DIR` est défini. Les tests de démarrage isolent leurs fichiers dans `build/probe-userdata`.

Le rendu Vulkan est sélectionné par défaut. Le paramètre `gpu_renderer=0` dans `dist/userdata/settings.ini` sélectionne le rendu logiciel affiché via Direct3D 11.

`-WithGpuShaders` télécharge la version Windows x64 de DXC 1.8.2505.1 pour compiler les shaders Vulkan additionnels. Pour utiliser une autre installation de DXC compatible SPIR-V, passer son chemin via `-DLGM2_DXC=...` à CMake. [Version Microsoft DXC 1.8.2505.1](https://github.com/microsoft/DirectXShaderCompiler/releases/tag/v1.8.2505.1)
