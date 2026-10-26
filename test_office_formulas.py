import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QTableWidgetItem,QStyleOptionViewItem,QTableWidgetSelectionRange
from PySide6.QtTest import QTest
from openpyxl import load_workbook
from office_suite import Tables
from office_formulas import calculate_cell,FormulaError,recalculate,NUMBER_FORMAT_ROLE
from office_cells import format_cells
from office_spreadsheets import chart_values
from office_ribbon import install_ribbon


class FormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    def painted(self,editor,row,col):
        option=QStyleOptionViewItem();editor.grid.itemDelegate().initStyleOption(option,editor.grid.model().index(row,col));return option.text

    def test_result_display_editing_automatic_recalc_charts_and_native_save(self):
        editor=Tables()
        for r,row in enumerate([['Item','Count','Price','Total'],['One','1','12.5','=B2*C2'],['Two','2','12.5','=B3*C3']]):
            for c,value in enumerate(row):editor.grid.setItem(r,c,QTableWidgetItem(value))
        QTest.qWait(180);self.assertEqual(self.painted(editor,1,3),'12.5');self.assertEqual(self.painted(editor,2,3),'25')
        editor.grid.setCurrentCell(1,3);self.assertEqual(editor.formula.text(),'=B2*C2')
        delegate=editor.grid.itemDelegate();index=editor.grid.model().index(1,3);field=delegate.createEditor(editor.grid,QStyleOptionViewItem(),index);delegate.setEditorData(field,index);self.assertEqual(field.text(),'=B2*C2');field.deleteLater()
        editor.grid.item(1,1).setText('4');QTest.qWait(180);self.assertEqual(self.painted(editor,1,3),'50')
        format_cells(editor,number_format='0.00');self.assertEqual(self.painted(editor,1,3),'50.00')
        editor.formula.setText('=ROUND(B2*C2,1)');editor._apply_formula();QTest.qWait(180)
        self.assertEqual(editor.grid.item(1,3).data(NUMBER_FORMAT_ROLE),'0.00')
        self.assertEqual(chart_values(editor,(1,1,3,4))['series'][-1]['values'],[50.0,25.0])
        install_ribbon(editor);toggle=editor.ribbon_buttons['Show formulas'].defaultAction();editor.dirty=False;toggle.setChecked(True)
        self.assertEqual(self.painted(editor,1,3),'=ROUND(B2*C2,1)');self.assertFalse(editor.dirty);toggle.setChecked(False)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'formulas.xlsx';editor._write(path);book=load_workbook(path);self.assertEqual(book.active['D2'].value,'=ROUND(B2*C2,1)');book.close()
            loaded=Tables();loaded._read(path);self.assertEqual(self.painted(loaded,1,3),'50.00');self.assertEqual(loaded.grid.item(1,3).text(),'=ROUND(B2*C2,1)')

    def test_functions_errors_absolute_refs_and_lazy_conditions(self):
        cases={'=SUM($A$1:A2)':3,'=COUNT(A1:A3)':2,'=COUNTA(A1:A4)':3,'=IF(A1=1,ROUND(2.675,2),1/0)':2.68,'=IFERROR(1/0,7)':7,'=ABS(-9)':9,'=AND(A1>0,A2<5)':True,'=OR(FALSE,TRUE)':True,'=NOT(FALSE)':True,'=IF(TRUE,4,#N/A)':4}
        for formula,expected in cases.items():self.assertEqual(calculate_cell([['1'],['2'],[''],['Text'],[formula]],'A5'),expected)
        for formula,code in [('=1/0','#DIV/0!'),('=A1+1','#CYCLE!'),('=VLOOKUP(1,A2:B3,2)','#NAME?'),('=A1048577','#REF!'),('=2^1000','#NUM!'),('="unclosed','#VALUE!')]:
            with self.assertRaises(FormulaError) as caught:calculate_cell([[formula]],'A1')
            self.assertEqual(caught.exception.code,code)
        editor=Tables();editor.grid.setItem(0,0,QTableWidgetItem('=1/0'));recalculate(editor);self.assertEqual(self.painted(editor,0,0),'#DIV/0!')

    def test_autosum_refuses_overwrite_and_replacing_formula_clears_result_roles(self):
        editor=Tables();editor.grid.setItem(0,0,QTableWidgetItem('1'));editor.grid.setItem(1,0,QTableWidgetItem('2'));install_ribbon(editor)
        editor.grid.setRangeSelected(QTableWidgetSelectionRange(0,0,1,0),True);editor.ribbon_buttons['AutoSum'].click();recalculate(editor)
        self.assertEqual(editor.grid.item(2,0).text(),'=SUM(A1:A2)');self.assertEqual(self.painted(editor,2,0),'3')
        editor.grid.item(2,0).setText('Literal');recalculate(editor)
        self.assertEqual(self.painted(editor,2,0),'Literal');self.assertIsNone(editor.grid.item(2,0).data(Qt.AccessibleTextRole));self.assertEqual(editor.grid.item(2,0).toolTip(),'')
        editor.grid.clearSelection();editor.grid.setRangeSelected(QTableWidgetSelectionRange(0,0,1,0),True)
        with patch('PySide6.QtWidgets.QMessageBox.warning') as warning:editor.ribbon_buttons['AutoSum'].click();self.assertTrue(warning.called)
        self.assertEqual(editor.grid.item(2,0).text(),'Literal')


if __name__=='__main__':unittest.main()
