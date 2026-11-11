"""Presentation/template packages and optional legacy-format interoperability."""
import io,tempfile
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from pptx import Presentation
from pptx.opc.constants import CONTENT_TYPE as CT

NATIVE={'.pptx':CT.PML_PRESENTATION_MAIN,'.potx':CT.PML_TEMPLATE_MAIN,'.ppsx':CT.PML_SLIDESHOW_MAIN}
IMPORTS=set(NATIVE)|{'.odp','.ppt'}
EXPORTS=set(NATIVE)|{'.odp'}


def package_kind(blob,suffix):
    if suffix not in NATIVE:raise ValueError('Choose PPTX, POTX or PPSX.')
    result=io.BytesIO()
    with ZipFile(io.BytesIO(blob)) as source,ZipFile(result,'w') as target:
        entries=source.infolist()
        if len(entries)>20000 or sum(info.file_size for info in entries)>2*1024**3:raise ValueError('The presentation package is too large to normalize safely.')
        for info in entries:
            data=source.read(info)
            if info.filename=='[Content_Types].xml':
                root=etree.fromstring(data,etree.XMLParser(resolve_entities=False,no_network=True))
                for node in root:
                    if node.get('PartName')=='/ppt/presentation.xml':node.set('ContentType',NATIVE[suffix])
                data=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
            target.writestr(info,data)
    return result.getvalue()


def load(path):
    path=Path(path);suffix=path.suffix.lower()
    if suffix not in IMPORTS:raise ValueError('Choose PPTX, POTX, PPSX, ODP or PPT.')
    if suffix in NATIVE:
        if suffix=='.pptx':return Presentation(path)
        if path.stat().st_size>512*1024**2:raise ValueError('Choose a template or slideshow smaller than 512 MB.')
        return Presentation(io.BytesIO(package_kind(path.read_bytes(),'.pptx')))
    from office_pdf import convert_with_libreoffice
    with tempfile.TemporaryDirectory(prefix='dazzle-import-') as temporary:
        target=Path(temporary)/'converted.pptx';convert_with_libreoffice(path,target);return Presentation(target)


def export(blob,suffix):
    if suffix in NATIVE:return package_kind(blob,suffix)
    if suffix!='.odp':raise ValueError('Choose PPTX, POTX, PPSX or ODP.')
    from office_pdf import convert_with_libreoffice
    with tempfile.TemporaryDirectory(prefix='dazzle-export-') as temporary:
        source=Path(temporary)/'source.pptx';source.write_bytes(blob);target=Path(temporary)/'converted.odp';convert_with_libreoffice(source,target);return target.read_bytes()
