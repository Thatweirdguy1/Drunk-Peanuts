"""Native, scrollable ribbon shared by the Office workspaces."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QToolButton,QToolBar,QTabWidget,QScrollArea,QComboBox,QWidgetAction,QSizePolicy)
from ui import icon,palette


def install_ribbon(window):
    if hasattr(window,'ribbon'):return
    bars=window.findChildren(QToolBar,options=Qt.FindDirectChildrenOnly)
    window._ribbon_source_bars=bars
    menus=[a.menu() for a in window.menuBar().actions() if a.menu()]
    actions=[];locations={};widgets=[]
    for menu in menus:
        for action in menu.actions():
            if not action.isSeparator():
                if action not in actions:actions.append(action)
                locations.setdefault(action,menu.title().replace('&',''))
    for bar in bars:
        for action in bar.actions():
            if isinstance(action,QWidgetAction) and action.defaultWidget():
                widget=action.defaultWidget()
                if not isinstance(widget,QLabel):widgets.append((bar,action,widget))
            elif not action.isSeparator() and action not in actions:actions.append(action)
    panel=QWidget();panel.setObjectName('officeRibbon');layout=QVBoxLayout(panel);layout.setContentsMargins(5,0,5,0);layout.setSpacing(2)
    quick=QHBoxLayout();quick.setContentsMargins(8,0,8,0)
    brand=QLabel('Drunk Peanuts.');brand.setStyleSheet('color:#ffdd22;font:bold italic 17px Georgia');quick.addWidget(brand)
    for label in ('Save','Undo','Redo'):
        action=next((a for a in actions if a.text().replace('&','')==label),None)
        if action:
            button=QToolButton();button.setDefaultAction(action);button.setIconSize(QSize(18,18));quick.addWidget(button)
    quick.addStretch()
    search=QComboBox();search.setEditable(True);search.setInsertPolicy(QComboBox.NoInsert);search.setMinimumWidth(240);search.setMaximumWidth(360);search.setAccessibleName('Search commands');search.lineEdit().setPlaceholderText('Search commands…')
    searchable=[a for a in actions if not a.menu()];search.addItems([a.text().replace('&','') for a in searchable]);search.setCurrentIndex(-1);search.completer().setCaseSensitivity(Qt.CaseInsensitive)
    def run_command(index):
        if 0<=index<len(searchable):searchable[index].trigger();search.setCurrentIndex(-1)
    search.activated.connect(run_command);quick.addWidget(search);layout.addLayout(quick)
    tabs=QTabWidget();tabs.setObjectName('ribbonTabs');tabs.setAccessibleName('Office ribbon tabs');tabs.setDocumentMode(True);layout.addWidget(tabs)
    window.ribbon=tabs;window.command_search=search;window.ribbon_buttons={}
    window._ribbon_actions=actions
    pages={};groups={}
    name=window.windowTitle().split(' ·')[0]
    is_slides=name=='Dazzle';is_tables=name=='Tables'
    order=['File','Home','Insert','Design','Transitions','Animations','Slide show','Arrange','View','Templates'] if is_slides else ['File','Home','Insert','Layout','Data','Formulas','Review','View','Templates'] if is_tables else ['File','Home','Insert','Layout','Review','View','Templates']
    def destination(action):
        label=action.text().replace('&','');menu=locations.get(action,'Home')
        if menu=='File':return 'File','Document'
        if menu=='Templates':return 'Templates','Starters'
        if menu in ('Insert','Layout','Data','Formulas','Review','View','Animations'):return menu,menu
        if menu=='Design':
            if label in ('Bold','Italic','Underline'):return 'Home','Font'
            if 'transition' in label.lower():return 'Transitions','Slide transition'
            return 'Design','Slide design'
        if menu=='Slide':return ('Slide show','Present') if label in ('Slideshow','Present from beginning') else ('View','Speaker notes') if label=='Speaker notes' else ('Home','Slides')
        if menu=='Arrange':return 'Arrange','Objects'
        if label in ('Cut','Copy','Paste','Undo','Redo'):return 'Home','Clipboard'
        if label in ('Bold','Italic','Underline','Text color','Highlight','Clear formatting','Strikethrough','Superscript','Subscript'):return 'Home','Font'
        if label.startswith('Align') or label in ('Bullets','Numbering','Line spacing','Indent','Outdent'):return 'Home','Paragraph' if not is_tables else 'Alignment'
        if label in ('Add slide','Delete slide','Duplicate slide'):return 'Home','Slides'
        if label=='Normal' or label.startswith('Heading '):return 'Home','Styles'
        return 'Home','Editing'
    def group(tab,title):
        key=(tab,title)
        if key in groups:return groups[key]
        if tab not in pages:
            area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QScrollArea.NoFrame);area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            content=QWidget();row=QHBoxLayout(content);row.setContentsMargins(4,2,4,2);row.setSpacing(0);area.setWidget(content);pages[tab]=(area,row)
        frame=QWidget();frame.setObjectName('ribbonGroup');box=QVBoxLayout(frame);box.setContentsMargins(8,1,8,0);box.setSpacing(1);grid=QGridLayout();grid.setSpacing(2);box.addLayout(grid,1)
        caption=QLabel(title);caption.setAlignment(Qt.AlignCenter);caption.setObjectName('ribbonCaption');box.addWidget(caption);pages[tab][1].addWidget(frame);groups[key]=(grid,frame)
        return grid,frame
    for action in actions:
        window.addAction(action)  # Keep shortcuts active while their tab is hidden.
        tab,title=destination(action);grid,frame=group(tab,title);button=QToolButton(frame);button.setDefaultAction(action)
        if action.menu():button.setMenu(action.menu());button.setPopupMode(QToolButton.InstantPopup)
        if action.icon().isNull():
            label=action.text().lower();glyph='chart' if 'chart' in label or 'graph' in label else 'import' if 'image' in label else 'table' if 'table' in label else 'play' if 'video' in label else 'color' if 'color' in label or 'background' in label else 'pen' if 'shape' in label else 'new' if 'break' in label else 'settings'
            action.setIcon(icon(glyph,palette()['accent']));action.setProperty('iconName',glyph)
        button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon);button.setIconSize(QSize(18,18));button.setMinimumHeight(29);button.setMaximumWidth(190);button.setAccessibleName(action.text().replace('&',''))
        if action.text().replace('&','') in ('Bold','Italic','Underline','Strikethrough','Superscript','Subscript','Align left','Align center','Align right'):
            button.setToolButtonStyle(Qt.ToolButtonIconOnly);button.setToolTip(action.text());button.setMinimumWidth(30)
        index=grid.count();grid.addWidget(button,index%2,index//2);window.ribbon_buttons[action.text().replace('&','')]=button
    widget_bars=list(dict.fromkeys(bar for bar,action,widget in widgets))
    for bar in widget_bars:
        grid,frame=group('Home','Font' if hasattr(window,'font_family') else 'Options')
        if grid.count():
            positions=[(grid.itemAt(i).widget(),grid.getItemPosition(i)) for i in range(grid.count())]
            for old,position in positions:grid.removeWidget(old);grid.addWidget(old,position[0]+1,position[1],position[2],position[3])
        for action in list(bar.actions()):
            if not isinstance(action,QWidgetAction):bar.removeAction(action)
        width=sum(min(widget.maximumWidth(),widget.sizeHint().width()) for source,action,widget in widgets if source is bar)+32
        window.removeToolBar(bar);bar.setParent(frame);bar.setMinimumWidth(width);bar.setStyleSheet('QToolBar {padding:0;border:0;}');grid.addWidget(bar,0,0,1,max(1,grid.columnCount()));bar.show()
    for title in order+[t for t in pages if t not in order]:
        if title in pages:
            area,row=pages[title];row.addStretch();tabs.addTab(area,title)
    tabs.setCurrentIndex(next((i for i in range(tabs.count()) if tabs.tabText(i)=='Home'),0))
    container=QToolBar('Ribbon',window);container.setObjectName('ribbonContainer');container.setIconSize(QSize(18,18));container.setMovable(False);container.addWidget(panel);window.addToolBar(Qt.TopToolBarArea,container)
    for bar in bars:
        if bar not in widget_bars:window.removeToolBar(bar);bar.hide()
    window.menuBar().hide();panel.setMinimumWidth(0);panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);tabs.setFixedHeight(168)

