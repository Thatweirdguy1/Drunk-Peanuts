"""Shared local chart data, images and media insertion helpers."""
from __future__ import annotations
import csv
import io
import math
import subprocess
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QFont
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QComboBox, QPlainTextEdit, QLabel, QMessageBox

CHART_TYPES = ('Column', 'Bar', 'Line', 'Pie', 'Scatter')
COLORS = ('#ffdd22', '#7dc4c0', '#f59b65', '#a69ee8', '#eeeeee')

def chart_data(text):
    rows = list(csv.reader(io.StringIO(text)))
    if not 2 <= len(rows) <= 501 or not 2 <= len(rows[0]) <= 9:
        raise ValueError('Use a header and 1–500 data rows, with a category and 1–8 series.')
    width = len(rows[0])
    if any(len(row) != width for row in rows) or any(not value.strip() for value in rows[0]):
        raise ValueError('Every row must have the same number of columns and named headers.')
    values = [[float(value) for value in row[1:]] for row in rows[1:]]
    if not all(math.isfinite(value) for row in values for value in row):
        raise ValueError('Chart values must be finite numbers.')
    return {'categories': [row[0] for row in rows[1:]], 'series': [
        {'name': rows[0][col], 'values': [row[col-1] for row in values]} for col in range(1,width)]}

def ask_chart(parent, initial=None, kind='Column'):
    dialog = QDialog(parent); dialog.setWindowTitle('Insert chart · editable data')
    layout = QVBoxLayout(dialog)
    kinds = QComboBox(); kinds.addItems(CHART_TYPES); kinds.setCurrentText(kind)
    kinds.setAccessibleName('Chart type'); layout.addWidget(kinds)
    layout.addWidget(QLabel('CSV data: first row is the header; first column is the category (numeric X for scatter).'))
    text = QPlainTextEdit(); text.setAccessibleName('Chart data')
    if initial:
        stream=io.StringIO(); writer=csv.writer(stream)
        writer.writerow(['Category']+[s['name'] for s in initial['series']])
        writer.writerows([category]+[s['values'][i] for s in initial['series']] for i,category in enumerate(initial['categories']))
        text.setPlainText(stream.getvalue())
    else: text.setPlainText('Quarter,Revenue,Costs\nQ1,12,8\nQ2,18,10\nQ3,25,13\nQ4,32,16')
    layout.addWidget(text)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);layout.addWidget(buttons)
    result=[]
    def accept():
        try:
            data=chart_data(text.toPlainText()); validate_chart(data,kinds.currentText())
        except ValueError as error:
            QMessageBox.warning(dialog,'Chart data',str(error));return
        result.append((kinds.currentText(),data));dialog.accept()
    buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
    dialog.resize(650,430)
    return result[0] if dialog.exec()==QDialog.Accepted else None

def validate_chart(data, kind):
    if kind not in CHART_TYPES or not data['categories'] or not data['series']:
        raise ValueError('Choose a supported chart and nonempty data.')
    for series in data['series']:
        if len(series['values']) != len(data['categories']) or not all(math.isfinite(float(v)) for v in series['values']):
            raise ValueError('Series must have one finite value per category.')
    if kind=='Pie' and (len(data['series'])!=1 or any(v<0 for v in data['series'][0]['values']) or sum(data['series'][0]['values'])<=0):
        raise ValueError('Pie charts need one series of nonnegative values with a positive total.')
    if kind=='Scatter' and not all(math.isfinite(float(v)) for v in data['categories']):
        raise ValueError('Scatter chart categories must be numeric X values.')

def chart_png(data, kind='Column', width=900, height=500):
    validate_chart(data,kind)
    image=QImage(width,height,QImage.Format_ARGB32);image.fill(QColor('#ffffff'))
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);painter.setFont(QFont('Arial',12))
    left,top,right,bottom=65,45,width-25,height-70
    plotw,ploth=right-left,bottom-top
    values=[float(v) for s in data['series'] for v in s['values']]
    low,high=min(0,min(values)),max(0,max(values));high=high if high!=low else low+1
    y=lambda v:bottom-(float(v)-low)/(high-low)*ploth
    painter.setPen(QPen(QColor('#444444'),1));painter.drawLine(left,top,left,bottom);painter.drawLine(left,round(y(0)),right,round(y(0)))
    count=len(data['categories']);series_count=len(data['series'])
    for k in range(5):
        value=low+(high-low)*k/4
        if kind=='Bar':painter.drawText(round(left+(value-low)/(high-low)*plotw)-12,bottom+25,f'{value:g}')
        else:painter.drawText(2,round(y(value))+5,f'{value:g}')
    if kind=='Pie':
        angle=0;total=sum(values);rect=QRectF(left+plotw*.15,top,ploth,ploth)
        for index,value in enumerate(values):
            painter.setBrush(QColor(COLORS[index%len(COLORS)]));span=round(value/total*5760)
            painter.drawPie(rect,angle,span);angle+=span
    else:
        xs=[float(v) for v in data['categories']] if kind=='Scatter' else list(range(count))
        xmin,xmax=min(xs),max(xs);xmax=xmax if xmax!=xmin else xmin+1
        for si,series in enumerate(data['series']):
            color=QColor(COLORS[si%len(COLORS)]);painter.setPen(QPen(color,3));painter.setBrush(color)
            previous=None
            for i,value in enumerate(series['values']):
                x=left+(i+.5)/count*plotw;cy=y(value)
                if kind=='Scatter':x=left+(xs[i]-xmin)/(xmax-xmin)*plotw
                if kind=='Column':
                    bw=plotw/count*.75/series_count
                    painter.drawRect(QRectF(x-plotw/count*.375+si*bw,min(cy,y(0)),max(1,bw-2),abs(cy-y(0))))
                elif kind=='Bar':
                    bh=ploth/count*.75/series_count;zero=left+(0-low)/(high-low)*plotw;end=left+(value-low)/(high-low)*plotw
                    painter.drawRect(QRectF(min(zero,end),top+(i+.125)/count*ploth+si*bh,abs(end-zero),max(1,bh-2)))
                else:
                    if previous and kind=='Line':painter.drawLine(previous[0],previous[1],round(x),round(cy))
                    painter.drawEllipse(QRectF(x-4,cy-4,8,8));previous=(round(x),round(cy))
    painter.setPen(QColor('#333333'))
    for i,label in enumerate(data['categories']):
        if count<=20 or i%max(1,count//10)==0:
            if kind=='Bar':painter.drawText(QRectF(1,top+i/count*ploth,left-5,ploth/count),Qt.AlignVCenter|Qt.AlignRight,str(label)[:12])
            else:painter.drawText(QRectF(left+i/count*plotw,bottom+8,plotw/count,25),Qt.AlignCenter,str(label)[:12])
    for i,s in enumerate(data['series']):
        painter.setPen(QColor(COLORS[i%len(COLORS)]));painter.drawText(65+i*180,25,s['name'][:22])
    painter.end();buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return bytes(buffer.data())

def image_bytes(path):
    path=Path(path)
    if path.stat().st_size>64*1024*1024:raise ValueError('Choose an image smaller than 64 MB.')
    image=QImage(str(path))
    if image.isNull():raise ValueError('This image cannot be decoded. Choose PNG, JPEG, BMP or WebP.')
    if image.width()*image.height()>50_000_000:raise ValueError('Choose an image with fewer than 50 million pixels.')
    buffer=QBuffer();buffer.open(QIODevice.WriteOnly);image.save(buffer,'PNG');return bytes(buffer.data())

def video_poster(path):
    import imageio_ffmpeg
    path=Path(path)
    if path.stat().st_size>128*1024*1024:raise ValueError('Choose a video smaller than 128 MB for embedding.')
    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(path),'-frames:v','1','-vf','scale=640:-1','-f','image2pipe','-vcodec','png','-'],capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or not result.stdout:raise ValueError('Could not read a video frame.')
    return result.stdout
