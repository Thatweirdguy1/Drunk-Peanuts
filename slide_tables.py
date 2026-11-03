"""Native table structure and formatting, edited on a copy until Save."""
import copy
from pptx.shapes.shapetree import SlideShapeFactory
from pptx.dml.color import RGBColor
from pptx.util import Pt
from pptx.table import _Cell
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,
    QPushButton,QDialogButtonBox,QMessageBox,QColorDialog,QInputDialog)
from PySide6.QtGui import QColor


def structural_edit(table,axis,index,insert):
    if axis not in ('row','column'):raise ValueError('Choose rows or columns.')
    count=len(table.rows) if axis=='row' else len(table.columns)
    if not 0<=index<(count+1 if insert else count):raise ValueError('Choose a valid table position.')
    if not insert and count==1:raise ValueError('A table needs at least one row and column.')
    if insert and count>=(100 if axis=='row' else 40):raise ValueError('Table limit: 100 rows and 40 columns.')
    if any(c.is_merge_origin or c.is_spanned for row in table.rows for c in row.cells):
        raise ValueError('Split merged cells before adding or deleting rows or columns.')
    root=table._tbl
    if axis=='row':
        rows=list(root.tr_lst)
        if insert:
            node=copy.deepcopy(rows[min(index,count-1)])
            for cell in node.tc_lst:_Cell(cell,table).text=''
            if index==count:root.append(node)
            else:root.insert(list(root).index(rows[index]),node)
        else:root.remove(rows[index])
    else:
        grid=root.tblGrid;columns=list(grid.gridCol_lst)
        if insert:
            grid.insert(index,copy.deepcopy(columns[min(index,count-1)]))
            for row in root.tr_lst:
                cell=copy.deepcopy(row.tc_lst[min(index,count-1)]);_Cell(cell,table).text='';row.insert(index,cell)
        else:
            grid.remove(columns[index])
            for row in root.tr_lst:row.remove(row.tc_lst[index])


def table_dialog(editor,shape=None):
    shape=shape if shape is not None else editor.selected_shape()
    if shape is None or not shape.has_table:raise ValueError('Select a table first.')
    working=SlideShapeFactory(copy.deepcopy(shape._element),shape._parent);table=working.table
    dialog=QDialog(editor);dialog.setWindowTitle('Edit table');dialog.resize(950,640)
    layout=QVBoxLayout(dialog);grid=QTableWidget();grid.setAccessibleName('Slide table cells');layout.addWidget(grid,1)
    def refresh():
        grid.blockSignals(True);grid.clearSpans();grid.setRowCount(len(table.rows));grid.setColumnCount(len(table.columns))
        for r,row in enumerate(table.rows):
            for c,cell in enumerate(row.cells):
                item=QTableWidgetItem(cell.text)
                if cell.is_spanned:item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                grid.setItem(r,c,item)
                if cell.is_merge_origin:grid.setSpan(r,c,cell.span_height,cell.span_width)
        grid.blockSignals(False)
    def changed(item):
        cell=table.cell(item.row(),item.column())
        if not cell.is_spanned:cell.text=item.text()
    grid.itemChanged.connect(changed)
    def region():
        selected=grid.selectedRanges()
        if not selected:raise ValueError('Select table cells first.')
        if len(selected)!=1:raise ValueError('Select one rectangular cell range.')
        block=selected[0];return block.topRow(),block.leftColumn(),block.bottomRow(),block.rightColumn()
    def structural(axis,insert):
        position=grid.currentRow() if axis=='row' else grid.currentColumn()
        structural_edit(table,axis,max(0,position),insert);refresh()
    def merge():
        r,c,last_r,last_c=region()
        if r==last_r and c==last_c:raise ValueError('Select at least two adjacent cells.')
        table.cell(r,c).merge(table.cell(last_r,last_c));refresh()
    def split():
        r,c,rr,cc=region()
        for row in range(r,rr+1):
            for col in range(c,cc+1):
                if table.cell(row,col).is_merge_origin:table.cell(row,col).split()
        refresh()
    def fill():
        r,c,rr,cc=region();color=QColorDialog.getColor(QColor('#1b325f'),dialog,'Cell fill')
        if color.isValid():
            for row in range(r,rr+1):
                for col in range(c,cc+1):
                    cell=table.cell(row,col);cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string(color.name()[1:])
    def size(axis):
        position=grid.currentRow() if axis=='row' else grid.currentColumn()
        collection=table.rows if axis=='row' else table.columns
        if position<0:raise ValueError('Select a cell first.')
        attribute='height' if axis=='row' else 'width';current=getattr(collection[position],attribute)/12700
        value,ok=QInputDialog.getDouble(dialog,'Table dimensions',axis.title()+' size (points)',current,1,5000,1)
        if ok:setattr(collection[position],attribute,Pt(value))
    def style():
        for r,row in enumerate(table.rows):
            for cell in row.cells:
                cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string('1B325F' if r==0 else 'F5F3EB' if r%2 else 'E5E9F0')
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.color.rgb=RGBColor.from_string('FFFFFF' if r==0 else '202B3D');paragraph.font.bold=r==0
                    for run in paragraph.runs:run.font.color.rgb=paragraph.font.color.rgb;run.font.bold=r==0
    def guarded(callback):
        try:callback()
        except (ValueError,IndexError) as error:QMessageBox.warning(dialog,'Table',str(error))
    for controls in ([('Insert row',lambda:structural('row',True)),('Delete row',lambda:structural('row',False)),('Insert column',lambda:structural('column',True)),('Delete column',lambda:structural('column',False)),('Merge cells',merge),('Split cells',split)], [('Cell fill',fill),('Header and bands',style),('Row height',lambda:size('row')),('Column width',lambda:size('column'))]):
        row=QHBoxLayout();layout.addLayout(row)
        for label,callback in controls:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,fn=callback:guarded(fn));row.addWidget(button)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);refresh()
    if dialog.exec()==QDialog.Accepted:
        def commit():
            shape._element.getparent().replace(shape._element,working._element)
        editor.change(commit)
