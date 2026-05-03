from pathlib import Path

import pandas as pd
from tdxpy.reader import BlockReader

from mootdx.consts import TYPE_FLATS
from mootdx.consts import TYPE_GROUP
from mootdx.logger import logger


BLOCK_ALIASES = {
    'fg': 'block_fg.dat',
    'gn': 'block_gn.dat',
    'zs': 'block_zs.dat',
    'sb': 'sbblock.dat',
    'sp': 'spblock.dat',
    'hk': 'hkblock.dat',
    'jj': 'jjblock.dat',
    'mg': 'mgblock.dat',
    'uk': 'ukblock.dat',
}


class BaseParse:
    def __init__(self, tdxdir):  # noqa
        self.tdxdir = tdxdir  # noqa

    def block_files(self):
        """
        列出 T0002/hq_cache 下可解析的通达信板块文件

        :return: pd.DataFrame(columns=['name', 'filename', 'path'])
        """

        hq_cache = Path(self.tdxdir, 'T0002', 'hq_cache')
        rows = []

        for name, filename in BLOCK_ALIASES.items():
            path = hq_cache / filename

            if path.exists():
                rows.append({'name': name, 'filename': filename, 'path': str(path)})

        return pd.DataFrame(rows, columns=['name', 'filename', 'path'])

    def blocks(self, name='gn', group=False):
        """
        按通达信常见别名读取板块

        :param name: gn/fg/zs/sb/sp/hk/jj/mg/uk，或完整文件名
        :param group: 是否分组返回
        :return: pd.DataFrame
        """

        symbol = BLOCK_ALIASES.get(str(name).lower(), name)
        return self.parse(symbol=symbol, group=group)

    def parse(self, symbol=None, group=False, **kwargs):  # noqa
        """
        获取板块数据

        参考: http://blog.sina.com.cn/s/blog_623d2d280102vt8y.html

        :param symbol:  板块文件
        :param group:   分组解析
        :return: pd.dataFrame or None
        """

        symbol = BLOCK_ALIASES.get(str(symbol).lower(), symbol)
        suffix = Path(symbol).suffix or '.dat'
        symbol = Path(symbol).stem

        vipdoc = (Path('T0002', 'hq_cache'), '')['incon' in symbol]  # noqa
        vipdoc = Path(vipdoc, f'{symbol}{suffix}')  # noqa

        if not Path(self.tdxdir, vipdoc).exists():
            logger.error(f'文件不存在: {vipdoc}')
            return None

        if 'incon' in symbol:  # noqa
            return self.__incon(vipdoc)

        if 'block_' in symbol and suffix == '.dat':
            return BlockReader().get_df(str(Path(self.tdxdir, vipdoc)), (TYPE_FLATS, TYPE_GROUP)[bool(group)])

        return self.cfg(vipdoc)

    def read_text(self, path):
        return Path(self.tdxdir, path).read_text(encoding='gbk').strip()

    def __incon(self, path):  # noqa
        t = self.read_text(path)
        m = [x for x in t.split('######')]
        v = [n.split() for n in m if n.strip()]

        d = {i[0]: [c.split('|') for c in i[1:]] for i in v}
        d = {key: dict([vv for vv in val if len(vv) == 2]) for key, val in d.items()}

        return d

    def cfg(self, path):
        ts = self.read_text(path)
        ls = [ll.split('|') for ll in ts.split()]

        return pd.DataFrame(ls)
