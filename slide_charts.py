"""Native editable chart options and QPainter previews."""
import copy,math
from PySide6.QtCore import Qt,QRectF,QBuffer,QIODevice,QPointF
from PySide6.QtGui import QColor,QImage,QPainter,QFont,QPen,QPolygonF
from PySide6.QtWidgets import QDialog,QFormLayout,QLineEdit,QCheckBox,QDialogButtonBox
from pptx.enum.chart import XL_LEGEND_POSITION
from pptx.oxml.xmlchemy import OxmlElement

C='http://schemas.openxmlformats.org/drawingml/2006/chart'
A='http://schemas.openxmlformats.org/drawingml/2006/main'


def axes(chart):
    result={}
    for node in chart._chartSpace.findall('.//{'+C+'}valAx'):
        position=node.find('{'+C+'}axPos')
        if position is not None and position.get('val') in ('b','t'):
            from pptx.chart.axis import ValueAxis
            result['x']=ValueAxis(node)
        elif position is not None:
            from pptx.chart.axis import ValueAxis
            result['y']=ValueAxis(node)
    try:result['x']=chart.category_axis
    except ValueError:pass
    if 'y' not in result:
        try:result['y']=chart.value_axis
        except ValueError:pass
    return result


def combination(chart):
    plot=chart._chartSpace.find('.//{'+C+'}barChart')
    if plot is None:raise ValueError('Combination charts need a column plot.')
    series=plot.findall('{'+C+'}ser')
    if len(series)<2:raise ValueError('A column + line chart needs at least two series.')
    line=OxmlElement('c:lineChart');group=OxmlElement('c:grouping');group.set('val','standard');line.append(group)
    for source in series[1:]:plot.remove(source);line.append(source)
    for axis in plot.findall('{'+C+'}axId'):line.append(copy.deepcopy(axis))
    plot.getparent().insert(list(plot.getparent()).index(plot)+1,line)


def change_type(editor,shape,kind,data):
    from dazzle import CHARTS,native_chart_data
    from slide_rendering import P
    values=native_chart_data(kind,data);settings=options(shape.chart)
    def apply():
        shapes=editor.deck.slides[editor.index].shapes;created=shapes.add_chart(CHARTS[kind],shape.left,shape.top,shape.width,shape.height,values)
        if kind=='Column + line':combination(created.chart)
        apply_options(created.chart,settings);created.rotation=shape.rotation
        old=shape._element.find('.//{'+P+'}cNvPr');new=created._element.find('.//{'+P+'}cNvPr');new.getparent().replace(new,copy.deepcopy(old))
        parent=shape._element.getparent();parent.remove(created._element);parent.replace(shape._element,created._element)
        old_chart=shape._element.find('.//{'+C+'}chart')
        if old_chart is not None:
            rid=old_chart.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            if rid and not any(rid in node.attrib.values() for node in editor.deck.slides[editor.index]._element.iter()):shape.part.drop_rel(rid)
        return created
    created=editor.change(apply);editor.choose(created);return created


def options(chart,theme=None):
    def text(title):
        if title.has_text_frame:return title.text_frame.text
        return ' '.join(node.text or '' for node in title._element.findall('.//{'+C+'}v'))
    result={'title':text(chart.chart_title) if chart.has_title else '', 'legend':chart.has_legend,'labels':False,'x_title':'','y_title':'','minimum':None,'maximum':None,'colors':[]}
    for index,series in enumerate(chart.series):
        fallback='#'+theme.colors.get('accent'+str(index%6+1),'4472C4') if theme else ['#4472C4','#ED7D31','#A5A5A5','#FFC000','#5B9BD5','#70AD47'][index%6]
        fill=series._element.find('{'+C+'}spPr/{'+A+'}solidFill')
        result['colors'].append(theme.color(fill,fallback).name() if theme else fallback)
    result['labels']=any(plot._element.find('{'+C+'}dLbls') is not None for plot in chart.plots)
    for label,axis in axes(chart).items():
        result[label+'_title']=text(axis.axis_title) if axis.has_title else ''
        if label=='y':result['minimum']=axis.minimum_scale;result['maximum']=axis.maximum_scale
    return result


def apply_options(chart,settings):
    low,high=settings.get('minimum'),settings.get('maximum')
    if any(value is not None and not math.isfinite(value) for value in (low,high)) or low is not None and high is not None and low>=high:raise ValueError('Axis minimum must be less than its maximum, using finite values.')
    if any(len(settings.get(key,''))>500 for key in ('title','x_title','y_title')):raise ValueError('Chart and axis titles must be under 500 characters.')
    chart.has_title=bool(settings['title'])
    if chart.has_title:chart.chart_title.text_frame.text=settings['title']
    chart.has_legend=settings['legend']
    if chart.has_legend:chart.legend.position=XL_LEGEND_POSITION.BOTTOM
    for plot in chart.plots:
        for node in list(plot._element.findall('.//{'+C+'}dLbls')):node.getparent().remove(node)
        if settings['labels']:
            labels=OxmlElement('c:dLbls');show=OxmlElement('c:showVal');show.set('val','1');labels.append(show)
            series=plot._element.findall('{'+C+'}ser');plot._element.insert(list(plot._element).index(series[-1])+1 if series else len(plot._element),labels)
    for label,axis in axes(chart).items():
        key=label+'_title';axis.has_title=bool(settings[key])
        if axis.has_title:axis.axis_title.text_frame.text=settings[key]
        if label=='y':axis.minimum_scale=low;axis.maximum_scale=high


def settings_dialog(editor):
    shape=editor.selected_shape()
    if shape is None or not shape.has_chart:raise ValueError('Select a chart first.')
    values=options(shape.chart);dialog=QDialog(editor);dialog.setWindowTitle('Chart titles, axes and labels');form=QFormLayout(dialog);fields={}
    for key,label in [('title','Chart title'),('x_title','Category / X title'),('y_title','Value / Y title')]:field=QLineEdit(values[key]);field.setAccessibleName(label);fields[key]=field;form.addRow(label,field)
    legend=QCheckBox('Show legend');legend.setChecked(values['legend']);labels=QCheckBox('Show data labels');labels.setChecked(values['labels']);form.addRow(legend);form.addRow(labels)
    for key,label in [('minimum','Value axis minimum'),('maximum','Value axis maximum')]:
        row=QLineEdit('' if values[key] is None else str(values[key]));row.setPlaceholderText('Automatic');row.setAccessibleName(label);fields[key]=row;form.addRow(label,row)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
    if dialog.exec()==QDialog.Accepted:
        settings={key:field.text() for key,field in fields.items()};settings.update(legend=legend.isChecked(),labels=labels.isChecked())
        for key in ('minimum','maximum'):settings[key]=float(settings[key]) if settings[key].strip() else None
        editor.change(lambda:apply_options(shape.chart,settings))


def preview(data,kind,width=900,height=500,settings=None):
    settings=settings or {};image=QImage(width,height,QImage.Format_ARGB32);image.fill(Qt.white);painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);painter.setFont(QFont('Arial',11))
    colors=settings.get('colors') or ['#4472C4','#ED7D31','#A5A5A5','#FFC000','#5B9BD5','#70AD47'];labels=settings.get('labels',False);legend=settings.get('legend',True)
    left,top,right,bottom=75,45,width-30,height-(80 if legend else 50);pw,ph=right-left,bottom-top;count=len(data['categories']);series=data['series'];stacked=kind.startswith('Stacked');horizontal=kind in ('Bar','Stacked bar')
    values=[float(v) for value in series for v in value['values']]
    if stacked:
        sums=[sum(max(0,float(value['values'][i])) for value in series) for i in range(count)]+[sum(min(0,float(value['values'][i])) for value in series) for i in range(count)];values+=sums
    low=settings.get('minimum');high=settings.get('maximum');low=min(0,min(values)) if low is None else low;high=max(0,max(values)) if high is None else high
    if high<=low:high=low+1
    y=lambda value:bottom-(float(value)-low)/(high-low)*ph
    xvalue=lambda value:left+(float(value)-low)/(high-low)*pw
    x=lambda index:left+(index+.5)*pw/count
    try:
        painter.setPen(QColor('#202b3d'));painter.drawText(QRectF(left,5,pw,30),Qt.AlignCenter,settings.get('title',''))
        if kind in ('Pie','Doughnut'):
            total=sum(values);diameter=min(pw,ph)*.92;rect=QRectF(left+(pw-diameter)/2,top+(ph-diameter)/2,diameter,diameter);angle=90*16
            for i,value in enumerate(series[0]['values']):
                span=round(float(value)/total*5760);painter.setPen(Qt.NoPen);painter.setBrush(QColor(colors[i%len(colors)]));painter.drawPie(rect,angle,span)
                if labels:
                    theta=math.radians((angle+span/2)/16);point=rect.center()+QPointF(math.cos(theta)*diameter*.34,-math.sin(theta)*diameter*.34);painter.setPen(QColor('#101014'));painter.drawText(QRectF(point.x()-50,point.y()-10,100,24),Qt.AlignCenter,f"{data['categories'][i]}: {value:g}")
                angle+=span
            if kind=='Doughnut':painter.setPen(Qt.NoPen);painter.setBrush(Qt.white);painter.drawEllipse(rect.adjusted(diameter*.27,diameter*.27,-diameter*.27,-diameter*.27))
        else:
            painter.setPen(QPen(QColor('#dde1e8'),1))
            for step in range(5):
                value=low+(high-low)*step/4
                if horizontal:
                    xx=xvalue(value);painter.drawLine(QPointF(xx,top),QPointF(xx,bottom));painter.drawText(QRectF(xx-35,bottom+4,70,20),Qt.AlignCenter,f'{value:g}')
                else:
                    yy=y(value);painter.drawLine(QPointF(left,yy),QPointF(right,yy));painter.drawText(QRectF(17,yy-10,left-24,20),Qt.AlignRight|Qt.AlignVCenter,f'{value:g}')
            positive=[0.]*count;negative=[0.]*count;painter.save();painter.setClipRect(QRectF(left,top,pw,ph))
            for si,value in enumerate(series):
                color=QColor(colors[si%len(colors)]);painter.setPen(QPen(color,2.5));painter.setBrush(color);points=[];base=[]
                for i,raw in enumerate(value['values']):
                    v=float(raw);start=(positive[i] if v>=0 else negative[i]) if stacked else 0;end=start+v
                    if stacked:
                        if v>=0:positive[i]=end
                        else:negative[i]=end
                    column=kind in ('Column','Stacked column') or kind=='Column + line' and si==0
                    if column:
                        n=1 if stacked or kind=='Column + line' else len(series);bw=pw/count*.75/n;xx=x(i)-pw/count*.375+(0 if stacked else si)*bw;painter.drawRect(QRectF(xx,min(y(start),y(end)),max(1,bw-2),abs(y(end)-y(start))))
                    elif horizontal:
                        n=1 if stacked else len(series);bh=ph/count*.75/n;yy=top+(i+.125)*ph/count+(0 if stacked else si)*bh;painter.drawRect(QRectF(min(xvalue(start),xvalue(end)),yy,abs(xvalue(end)-xvalue(start)),max(1,bh-2)))
                    else:
                        xx=x(i)
                        if kind=='Scatter':
                            xs=[float(c) for c in data['categories']];minimum,maximum=min(xs),max(xs);xx=left+(float(data['categories'][i])-minimum)/max(1e-12,maximum-minimum)*pw
                        points.append(QPointF(xx,y(end if kind=='Stacked area' else v)));base.append(QPointF(xx,y(start)))
                    if labels and not horizontal:painter.drawText(QPointF(x(i)+3,y(end)-5),f'{v:g}')
                if points:
                    if kind in ('Area','Stacked area'):
                        fill=QColor(color);fill.setAlpha(150);painter.setBrush(fill);painter.drawPolygon(QPolygonF(points+list(reversed(base))))
                    else:
                        if kind!='Scatter':painter.drawPolyline(QPolygonF(points))
                        for point in points:painter.drawEllipse(point,3,3)
            painter.restore();painter.setPen(QColor('#333333'));stride=max(1,math.ceil(count/12))
            for i,label in enumerate(data['categories']):
                if i%stride and i!=count-1:continue
                if horizontal:painter.drawText(QRectF(2,top+i*ph/count,left-9,ph/count),Qt.AlignRight|Qt.AlignVCenter,str(label)[:20])
                else:painter.drawText(QRectF(x(i)-40,bottom+4,80,22),Qt.AlignCenter,str(label)[:18])
            painter.drawText(QRectF(left,height-(43 if legend else 24),pw,20),Qt.AlignCenter,settings.get('x_title',''));painter.save();painter.translate(12,(top+bottom)/2);painter.rotate(-90);painter.drawText(QRectF(-ph/2,-10,ph,20),Qt.AlignCenter,settings.get('y_title',''));painter.restore()
        if legend:
            entries=[(str(category),colors[i%len(colors)]) for i,category in enumerate(data['categories'])] if kind in ('Pie','Doughnut') else [(value['name'],colors[i%len(colors)]) for i,value in enumerate(series)]
            for i,(label,color) in enumerate(entries[:12]):
                cell=pw/max(1,min(12,len(entries)));xx=left+i*cell;painter.setPen(Qt.NoPen);painter.setBrush(QColor(color));painter.drawRect(QRectF(xx,height-23,10,10));painter.setPen(QColor('#333333'));painter.drawText(QRectF(xx+15,height-28,cell-18,20),Qt.AlignVCenter,label[:24])
    finally:painter.end()
    buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return bytes(buffer.data())
