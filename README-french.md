# watermark-pdf

watermark-pdf est une application de bureau (PyQt5) locale et hors ligne permettant d'ajouter un filigrane texte répété à vos fichiers PDF — un seul document ou un dossier entier d'un coup.

Tout s'exécute sur votre propre machine — vos documents ne sont jamais envoyés nulle part, et aucune connexion internet n'est nécessaire.

## Fonctionnalités

- **Fichier unique ou dossier entier** : ajoutez un filigrane à un PDF, ou à tous les PDF d'un dossier (sous-dossiers inclus en option, leur arborescence étant reproduite dans la sortie).
- **Aperçu en direct** : voyez exactement à quoi ressemblera le résultat pendant que vous tapez — même position, même angle, même taille de police et même interligne que le PDF généré — au format réel de votre document ou à un format standard (A3, A4, A5, Letter, Legal, en portrait ou en paysage).
- **Filigrane entièrement personnalisable** : texte sur plusieurs lignes, police (les 12 polices PDF standard), taille, couleur, opacité, angle de rotation, nombre de colonnes et de lignes, et marge de la page.
- **Sortie sûre** : les fichiers sont enregistrés avec le suffixe de votre choix (par ex. `report_watermarked.pdf`), ou écrasent les originaux si vous laissez le suffixe vide. Les fichiers sont écrits de manière atomique : un traitement interrompu ne laisse donc jamais un PDF à moitié écrit.
- **Fidèle au document d'origine** : les signets, les métadonnées, les liens et les champs de formulaire sont conservés ; les pages tournées et recadrées sont correctement gérées, de sorte que le filigrane apparaît toujours droit et centré.
- **Glisser-déposer** : déposez un PDF ou un dossier sur la fenêtre pour le sélectionner.
- **Progression et annulation** : barre de progression page par page, bouton d'annulation qui arrête immédiatement le traitement, et journal de chaque fichier créé.
- **Thème clair/sombre** et **5 langues** (anglais, français, espagnol, italien, allemand) ; vos réglages sont mémorisés d'une utilisation à l'autre.

## Installation

### Exécutables précompilés (recommandé pour la plupart des utilisateurs)

Téléchargez la dernière version pour votre plateforme depuis la [page des Releases](https://github.com/Artezaru/watermark-pdf/releases) :

- **Windows** : téléchargez et lancez directement `watermark-pdf-windows.exe` — aucune installation nécessaire.
- **Linux (Debian/Ubuntu)** : téléchargez le paquet `.deb` et installez-le avec :
  ```bash
  sudo dpkg -i watermark-pdf_*.deb
  ```
  watermark-pdf apparaîtra alors dans votre menu d'applications sous le nom *PDF Watermark*, ou pourra être lancé depuis un terminal avec `watermark-pdf`.

### Depuis les sources (développeurs)

Nécessite Python 3.10 ou une version ultérieure.

```bash
git clone https://github.com/Artezaru/watermark-pdf.git
cd watermark-pdf
pip install .
```

Lancez-le avec :

```bash
watermark-pdf
```

ou :

```bash
python -m watermark_pdf
```

## Utilisation en tant que bibliothèque Python

Le moteur de filigrane peut aussi être utilisé sans l'interface :

```python
from watermark_pdf.watermark import add_watermark, batch_watermark_directory

# Un fichier -> report_watermarked.pdf
add_watermark(
    "report.pdf",
    "CONFIDENTIAL\nDo not distribute",
    horizontal_boxes=3,
    vertical_boxes=6,
    opacity=0.15,
    angle=45,
    color="#DC2626",
    font="Helvetica-Bold",
    size=24,
)

# Tous les PDF d'un dossier -> documents_watermarked/
batch_watermark_directory("documents", "CONFIDENTIAL", recursive=True)
```

Installez la dépendance facultative `tqdm` (`pip install .[progress]`) pour obtenir une barre de progression dans la console.

## Compiler les exécutables vous-même

watermark-pdf utilise [PyInstaller](https://pyinstaller.org/) pour produire des exécutables autonomes. Depuis la racine du projet :

```bash
pip install pyinstaller pillow
pyinstaller --name watermark-pdf --windowed --onefile \
    --add-data "watermark_pdf/resources:watermark_pdf/resources" \
    --icon watermark_pdf/resources/app.png \
    watermark_pdf/__main__.py
```

(Sous Windows, remplacez le `:` de `--add-data` par `;`.)

Un workflow GitHub Actions est inclus (`.github/workflows/build.yml`) : il compile automatiquement les exécutables Windows et Linux (ainsi qu'un paquet `.deb`) et les publie dans une Release GitHub à chaque fois qu'un tag `v*` est poussé.

## Crédits

L'icône de l'application provient de Flaticon : <a href="https://www.flaticon.com/free-icons/watermark" title="watermark icons">Watermark icons created by Magnific - Flaticon</a>.

## Licence

watermark-pdf est un logiciel libre, distribué sous la **licence publique générale GNU v3.0 ou ultérieure** (GNU GPL v3.0 or later) — voir [LICENSE](LICENSE) pour le texte complet.

## Contribuer

Les signalements de bugs et les pull requests sont les bienvenus — merci d'ouvrir d'abord une issue sur le [tracker](https://github.com/Artezaru/watermark-pdf/issues) pour discuter de toute modification importante.
