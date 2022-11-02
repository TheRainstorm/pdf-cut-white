#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
from typing import List, Tuple

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import (
    LAParams,
    LTAnno,
    LTChar,
    LTContainer,
    LTCurve,
    LTFigure,
    LTImage,
    LTLine,
    LTRect,
    LTTextBox,
    LTTextLine,
)
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage, PDFTextExtractionNotAllowed
from pdfminer.pdfparser import PDFParser

from pdf_white_cut.logger import logger


def get_max_box(boxs: List) -> Tuple:
    down_left = [sys.maxsize, sys.maxsize]
    upper_right = [
        -sys.maxsize,
        -sys.maxsize,
    ]
    for box in boxs:
        if box is None:
            continue
        for idx, (cur, other) in enumerate(zip(down_left, box[0:2])):
            down_left[idx] = min(cur, other)
        for idx, (cur, other) in enumerate(zip(upper_right, box[2:])):
            upper_right[idx] = max(cur, other)

    return tuple(down_left) + tuple(upper_right)


def extract_item_box(item):
    """
    this is the core process logic for the tool
    which analyse all items in pdf type by type.
    """
    # no bbox for LTAnno
    if isinstance(item, LTAnno):
        return None

    # use bbox as default area
    bbox = item.bbox

    if isinstance(item, LTLine):
        logger.debug("use itself: {}", item)
    elif isinstance(item, LTRect):
        logger.debug("use itself: {}", item)
    elif isinstance(item, LTCurve):
        logger.debug("use itself: {}", item)
    elif isinstance(item, LTTextBox):
        logger.warning("NotImplemented and use itself: {}", item)
    elif isinstance(item, LTTextLine):
        # there is 2 types of `LTTextLine`: horizontal and vertical
        text = item.get_text().encode("unicode_escape")
        logger.debug("analyse LTTextLine: {} {}", item, text)
        # TODO: here we ignored fonts and text line direction, may error in some cases
        # since the text has a height on y-axis, or has a width on x-axis,
        # we must modify it to make the whole text visible
        # FIXME: no we use `half` for upper and lower, may not right but work
        bbox = (
            bbox[0] - item.width / 2,
            bbox[1] - item.height / 2,
            bbox[2] + item.width / 2,
            bbox[3] + item.height / 2,
        )
        return bbox

        # might check chart one by one
        # children_bbox = [extract_box(ch) for ch in item]
        # return get_max_box(children_bbox)
    elif isinstance(item, LTChar):
        text = item.get_text().encode("unicode_escape")
        logger.debug("analyse LTChar: {} {}", item, text)
        bbox = (
            bbox[0] - item.width / 2,
            bbox[1] - item.height / 2,
            bbox[2] + item.width / 2,
            bbox[3] + item.height / 2,
        )
    elif isinstance(item, LTImage):
        logger.warning("NotImplemented and use itself: {}", item)
    elif isinstance(item, LTFigure):
        logger.debug("analyse LTFigure:{}", item)
        # for `LTFigure`, the bbox is modified in `PDFMiner`
        # we should use the content item inside it to calculate real result
        try:
            children_bbox = []
            # _objs is the original items, of course, only one item for `LTFigure`
            for subfigure in item:
                # get all the item inside the figure
                if isinstance(subfigure, LTContainer):
                    children_bbox = [extract_item_box(item) for item in subfigure]
                    return get_max_box(children_bbox)
                break
        except Exception as e:
            logger.error("use default for error since no processor: {}", e)

    return bbox


def extract_pdf_boxs(filename, ignore=0):
    """
    use pdfminer to get the valid area of each page.
    all results are relative position!
    """
    # 打开一个pdf文件
    fp = open(filename, "rb")
    # 创建一个PDF文档解析器对象
    parser = PDFParser(fp)
    # 创建一个PDF文档对象存储文档结构
    # 提供密码初始化，没有就不用传该参数
    # document = PDFDocument(parser, password)
    document = PDFDocument(parser)
    # 检查文件是否允许文本提取
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed
    # 创建一个PDF资源管理器对象来存储共享资源
    # caching = False不缓存
    rsc_manager = PDFResourceManager(caching=False)
    # 创建一个PDF设备对象
    la_params = LAParams()
    # 创建一个PDF页面聚合对象
    device = PDFPageAggregator(rsc_manager, laparams=la_params)
    # 创建一个PDF解析器对象
    interpreter = PDFPageInterpreter(rsc_manager, device)
    # 处理文档当中的每个页面

    page_boxs = []

    for page in PDFPage.create_pages(document):
        interpreter.process_page(page)
        # 接受该页面的LTPage对象
        layout = device.get_result()
        # 这里layout是一个LTPage对象 里面存放着 这个page解析出的各种对象
        # 一般包括LTTextBox, LTFigure, LTImage, LTTextBoxHorizontal 等等
        boxs = []
        for item in layout:
            box = extract_item_box(item)

            # another process only for `LTRect` with `ignore`
            if isinstance(item, LTRect):
                logger.debug("rect:{}", item)
                # FIXME: some pdf has a global LTRect, case by case
                if ignore > 0:
                    ignore -= 1
                    continue
            boxs.append(box)

        max_box = get_max_box(boxs)
        logger.warning("visible bbox: {}", max_box)
        page_boxs.append(max_box)

        logger.warning("max visible bbox for the page: {}", max_box)
    return page_boxs
