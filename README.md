# Luigi’s Mansion 2 Recompiled

Portage communautaire expérimental de **Luigi’s Mansion 2** sur Windows x64. Le projet traduit le code ARM et Thumb de l’édition européenne 3DS (`CTR-P-AGGP`) en code natif et charge les ressources depuis une copie locale de la cartouche.

**Ta propre cartouche européenne est requise.** Le dépôt fournit le code du portage et les outils nécessaires à la compilation locale. L’image de la cartouche, ses ressources et l’exécutable recompilé restent sur ton PC.

## Construire et lancer

Suis le [guide de compilation](BUILD.md) pour préparer ta cartouche et compiler le projet. Ensuite, lance `dist/LuigisMansion2.exe`. Vulkan est sélectionné par défaut, avec un rendu logiciel disponible via Direct3D 11.

Le portage a été vérifié jusqu’au jardin de la mission A‑1, avec les déplacements, la lampe et la reprise d’un profil. La campagne complète et le multijoueur restent à valider. L’objectif de 60 FPS reste à atteindre. [Résultats des essais](PROGRESS.md)

## Commandes

| Commande 3DS | Clavier AZERTY |
| --- | --- |
| Stick circulaire | ZQSD |
| A / B / X / Y | K / J / I / U |
| L / R | Maj gauche / E |
| Start / Select | Entrée / Retour arrière |
| Écran tactile | Clic sur l’écran inférieur |

Les sauvegardes locales se trouvent sous `dist/userdata/games/0004000000076500/save`. Le programme conserve les versions précédentes dans `save-backups`.

Depuis le dossier du projet, lancer un essai avec la partition locale déjà extraite.

```powershell
.\dist\LuigisMansion2.exe .\extracted\LM2-EUR.cxi
```

Le test de la fonction de contrôle des sauvegardes exécute la traduction du code ARM d’origine et compare son résultat à un calcul indépendant.

## Contribuer

Les rapports de bugs et les contributions au code sont les bienvenus. Pour un problème de jeu, indique la mission ou l’écran concerné, la version de Windows, le mode de rendu et les étapes de reproduction. Les données du jeu, les clés et les sauvegardes doivent rester privées.

[Licence MIT du portage](LICENSE) · [Licence de Clockwork](licenses/Clockwork.txt)

```powershell
.\dist\LuigisMansion2.exe --verify-crc .\extracted\LM2-EUR.cxi
```

Le code généré, les binaires qui le contiennent et les ressources extraites sont destinés à rester dans ce dossier local. Les copies d’analyse et de test sont placées sous `extracted/`, `generated/`, `build/` et `logs/`.
