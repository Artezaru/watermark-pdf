# watermark-pdf

watermark-pdf est une application de bureau (PyQt5), locale et hors ligne, pour ajouter un filigrane texte à vos fichiers PDF, un seul document ou un dossier entier d'un coup.

Tout s'exécute sur votre propre machine : vos documents ne sont jamais envoyés nulle part, et aucune connexion internet n'est nécessaire.

![Interface de watermark-pdf](https://raw.githubusercontent.com/Artezaru/watermark-pdf/master/watermark_pdf/resources/ui.png)

## Fonctionnalités

- **Un fichier ou un dossier entier**, sous-dossiers inclus si vous le souhaitez.
- **Aperçu en direct** identique au PDF généré.
- **Filigrane personnalisable** : texte multiligne, police, taille, couleur, opacité, angle, grille et marge.
- **Sortie sûre** : fichiers enregistrés avec le suffixe de votre choix (ou écrasement des originaux), écrits de façon atomique.
- **Fidèle à l'original** : signets, métadonnées, liens et champs de formulaire sont conservés ; les pages pivotées ou rognées sont gérées.
- **Glisser-déposer**, barre de progression, annulation et journal.
- **Thème clair/sombre** et **5 langues** (anglais, français, espagnol, italien, allemand).

## Installation

### Exécutables prêts à l'emploi (recommandé)

Téléchargez la dernière version pour votre système depuis la [page Releases](https://github.com/Artezaru/watermark-pdf/releases) :

- **Windows** : téléchargez et lancez directement `watermark-pdf-windows.exe`, aucune installation nécessaire.
- **Linux (Debian/Ubuntu)** : téléchargez le paquet `.deb` et installez-le avec :
  ```bash
  sudo dpkg -i watermark-pdf_*.deb
  ```
  watermark-pdf apparaît alors dans le menu des applications sous le nom *PDF Watermark*, ou peut être lancé depuis un terminal avec `watermark-pdf`.

### Depuis les sources (développeurs)

Nécessite Python 3.10 ou plus récent.

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

## Utilisation comme bibliothèque Python

Le moteur de filigrane peut aussi être utilisé sans l'interface :

```python
from watermark_pdf.watermark import add_watermark, batch_watermark_directory

# Un fichier -> report_watermarked.pdf
add_watermark(
    "report.pdf",
    "CONFIDENTIEL\nNe pas diffuser",
    horizontal_boxes=3,
    vertical_boxes=6,
    opacity=0.15,
    angle=45,
    color="#DC2626",
    font="Helvetica-Bold",
    size=24,
)

# Tous les PDF d'un dossier -> documents_watermarked/
batch_watermark_directory("documents", "CONFIDENTIEL", recursive=True)
```

Installez la dépendance optionnelle `tqdm` (`pip install .[progress]`) pour afficher une barre de progression dans la console.

## Crédits

L'icône de l'application provient de Flaticon : <a href="https://www.flaticon.com/free-icons/watermark" title="watermark icons">Watermark icons created by Magnific - Flaticon</a>.

## Licence

watermark-pdf est un logiciel libre, sous licence **GNU General Public License v3.0 ou ultérieure**. Voir [LICENSE](LICENSE) pour le texte complet.

## Contribuer

Les rapports de bugs et les pull requests sont les bienvenus. Merci d'ouvrir d'abord un ticket sur le [tracker](https://github.com/Artezaru/watermark-pdf/issues) pour discuter de tout changement important.
