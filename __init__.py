from anki.hooks import addHook
from anki.utils import ids2str, intTime, splitFields

from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, showWarning

class RepositionByFieldDialog(QDialog):
    def __init__(self, browser, mid):
        super(RepositionByFieldDialog, self).__init__(browser)

        self.setWindowModality(Qt.WindowModal)
        self.setModal(True)
        self.setMinimumSize(300, 150)

        layout = QVBoxLayout()

        self.fieldList = QListWidget()
        self.fieldList.setMinimumSize(50, 60)
        layout.addWidget(self.fieldList)

        buttonBox = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self.setLayout(layout)
        self.setWindowTitle("Reposition New Cards by Field")

        self.chosenField = None
        self.chosenFieldName = None

        model = browser.col.models.get(mid)
        fieldNames = browser.col.models.fieldNames(model)

        self.fieldList.addItems(
                [str(i + 1) + ": " + f for i, f in enumerate(fieldNames)])

    def accept(self):
        super(RepositionByFieldDialog, self).accept()
        self.chosenField = self.fieldList.currentRow()
        self.chosenFieldName = self.fieldList.currentItem().text()


def repositionByField(browser):
    browser.editor.saveNow(lambda: _repositionByField(browser))

def _repositionByField(browser):
    cids = browser.selectedCards()
    scids = ids2str(cids)
    cids2 = browser.col.db.list(
            "select id from cards where type = 0 and id in " + scids)

    if not cids2:
        return showInfo(_("Only new cards can be repositioned."))

    mids = browser.col.db.list(
            """SELECT DISTINCT notes.mid FROM cards
               INNER JOIN notes ON cards.nid = notes.id
               WHERE cards.type = 0 AND cards.id IN """ + scids)

    if len(mids) != 1:
        return showInfo(
                "Only selections of a single card type are supported.")

    while True:
        browser.repositionByField = RepositionByFieldDialog(browser, mids[0])

        if not browser.repositionByField.exec_():
            browser.repositionByField = None
            return

        if browser.repositionByField.chosenField is None:
            showWarning("You must select a field to reposition.")
            continue

        try:
            chosenField = browser.repositionByField.chosenField
            updateCardPositions(browser, chosenField, cids)
        except ValueError:
            warntext = 'The chosen field "%s" contains non-numeric data.\n%s'
            warntext = warntext % (browser.repositionByField.chosenFieldName,
                    'Only numeric fields for the selected cards are supported.')
            showWarning(warntext)
            continue

        break

    browser.repositionByField = None

def updateCardPositions(browser, chosenField, cids):
    scids = ids2str(cids)
    now = intTime()
    d = []
    query = """SELECT cards.id, cards.nid, notes.flds
               FROM cards
               INNER JOIN notes ON cards.nid = notes.id
               WHERE cards.type = 0 AND cards.id IN """ + scids
    for id, nid, flds in browser.col.db.execute(query):
        fieldValue = int(splitFields(flds)[chosenField])
        d.append(dict(now=now, due=fieldValue, usn=browser.col.usn(), cid=id))
    browser.model.beginReset()
    browser.mw.checkpoint("Reposition by Field")
    browser.col.db.executemany(
            "update cards set due=:due,mod=:now,usn=:usn where id = :cid", d)
    browser.search()
    browser.mw.requireReset()
    browser.model.endReset()
    if len(d) == 1:
        showInfo("Repositioned %d card." % len(d))
    else:
        showInfo("Repositioned %d cards." % len(d))

def setupMenus(browser):
    action = QAction("Reposition by Field...", browser.form.menu_Cards)
    action.triggered.connect(lambda: repositionByField(browser))
    browser.form.menu_Cards.insertAction(browser.form.actionReposition, action)
    # All this second one does is swap the order so that mine comes last
    browser.form.menu_Cards.insertAction(action, browser.form.actionReposition)

addHook("browser.setupMenus", setupMenus)
