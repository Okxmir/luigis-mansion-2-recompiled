# État du portage

## Résultats vérifiés

- Cartouche européenne détectée et lue dans son emplacement d’origine. La partition exécutable est déchiffrée dans `extracted/LM2-EUR.cxi`. Les tests d’intégrité et l’inventaire sont dans `logs/extraction-integrity.txt` et `logs/extraction.txt`.
- Traduction statique ARM et Thumb en C, compilation MSVC x64 et chargement des segments de `LM3DS` à partir du CXI. La dernière génération contient 57 971 fonctions.
- La fonction originale `0x003B4B98` passe 84 comparaisons avec une référence CRC indépendante en Debug et Release. Les cas couvrent quatre alignements, plusieurs longueurs et trois états initiaux. Voir `logs/tests.txt` et `logs/tests-debug.txt`.
- Exécution du point d’entrée original `0x00100000`. Le premier blocage se situait dans la lecture de l’identité matérielle. La trace `logs/first-sleep.txt` documente la boucle. Le correctif PTM a supprimé ce blocage. L’analyse du démarrage a ensuite identifié un défaut de flot autour d’une trappe conditionnelle.
- Windows a affiché l’écran titre, la sélection de profil et la cinématique d’introduction via le rendu Vulkan sur la RTX 3080 Ti. Les captures sont dans `logs/mission-control` et `logs/vulkan-check-*.png`.
- Le jeu a écrit un `profile1.sav` de 3 895 octets dont les deux CRC ont été recalculés avec succès. Le profil existant a été retrouvé dans l’interface au redémarrage et son SHA-256 est resté identique pendant la migration des métadonnées. Voir `logs/resume-check-0.png` et `logs/boot-save-migrate.txt`.
- La version dans `dist/` a chargé la police et la partition locale depuis leurs emplacements par défaut. Elle a affiché la sélection du Manoir du désespoir et le briefing d’A-1. Voir `logs/mission-run/mission-a1.png` et `logs/mission-final.txt`.
- Le dernier exécutable dans `dist/` a affiché l’écran titre français avec ses réglages par défaut. Voir `logs/titre-final-0.png` et `logs/packaged-title.txt`.
- Après recompilation de la routine d’interpolation appelée au début d’A-1, Luigi a atteint le jardin. Les entrées du stick vers l’avant et la droite ont déplacé le personnage et orienté sa lampe. La position a changé sur la carte. Voir `logs/a1-retry/pret.png`, `logs/a1-retry/marche-avant.png`, `logs/a1-retry/marche-droite.png` et `logs/a1-retry/portail.png`.
- La sortie audio du test graphique contenait des échantillons non nuls à 32 728 Hz, en stéréo. La capture permet d’examiner le signal du mixeur.
- La commande `scripts/prepare.ps1 -CodeOnly` a reproduit l’extraction et la traduction à partir des dépendances épinglées. Une clé incorrecte est rejetée avant la publication de la partition extraite. L’empreinte de la cartouche originale correspond à celle relevée au départ.
- L’archive de sauvegarde est verrouillée par instance. Un deuxième lancement sur le même dossier a été refusé par Windows pendant le test, sans interrompre l’instance active. Voir `logs/save-lock-test.txt`.

## Validation en cours

Les premiers essais Vulkan présentaient des artefacts sur le sol, les marches et la grille du jardin. La première version utilisait le rendu logiciel avec affichage Direct3D 11 pour éviter ces défauts. La fin d’A-1, la sauvegarde de sa progression, les autres missions et ScareScraper restent à valider. Le portage utilise une police système de remplacement.

## Fluidité du rendu

Le rendu logiciel évite de décoder plusieurs fois les mêmes texels ETC, écarte plus tôt les pixels masqués et réduit les synchronisations entre les tâches de rendu. Le test sur le PC du projet a relevé environ 7 à 9 FPS dans le bunker avant ces changements et 13 à 16 FPS après. Le compteur `YW2_FPS` mesure les nouveaux tampons de l’écran supérieur sur des intervalles d’environ cinq secondes réelles. Les relevés se trouvent dans `logs/fps-cpu-before.txt` et `logs/fps-cpu-after.txt`.

Pendant la séquence d’arrivée en A‑1, les relevés du rendu logiciel se situent autour de 8 à 10 FPS avant et de 9 à 12 FPS après ces changements.

La version Vulkan suivante utilise une profondeur 16 bits quand le jeu demande ce format et lit directement les surfaces de taille native. Le test dans le jardin a affiché le sol et la grille sans les artefacts des premiers essais. Les déplacements et la lampe ont été vérifiés après l’appel du professeur. Voir `logs/fps-gpu-vertices/jardin-pret.png` et `logs/fps-gpu-vertices/jardin-apres.png`. Les calculs de sommets sur le processeur passent 11 778 comparaisons avec l’interpréteur de référence, en plus des 84 tests sur le CRC de sauvegarde.

Le nouvel exécutable dans `dist` choisit Vulkan par défaut et affiche directement l’écran inférieur en respectant la conversion RGB565. Sur la RTX 3080 Ti du projet, les mesures s’établissent autour de 20 à 23 FPS dans le bunker, de 18 à 19 FPS dans le jardin après l’introduction et de 17 à 18 FPS pendant le déplacement testé. Le mode expérimental `LGM2_GPU_VERTICES=1` a atteint 25 FPS dans le bunker et produit environ 15 FPS pendant le déplacement dans le jardin. La version livrée utilise donc les calculs de sommets x64. Les 60 FPS restent à atteindre. Voir `logs/fps-vulkan-final.txt` et les captures du dossier `logs/fps-vulkan-final/`.
