#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# __author__ = 'maximus'

import ruamel.yaml as yaml3ed
from collections import OrderedDict
import os
import logging
from zabbix import ZabbixAgent
from mapping import Node, Link, Map, Table, Palette, Singleton
from PIL import Image
import base64
import random
from io import BytesIO

log = logging.getLogger(__name__)


class ConfigException(Exception):
    def __init__(self, message):
        self.message = message

        # def __str__(self):
        #     return str(self.message).format(self.error)


class ConfigTemplate(metaclass=Singleton):  # noqa
    """ This is config template. DO NOT MODIFY THIS OBJECT."""

    def __init__(self):
        self.template = {'zabbix': {'url': str(), 'login': str(), 'password': str()},
                         'map': {'name': str(), 'bgcolor': str(), 'fontsize': 10, 'width': int(), 'height': int()},
                         'table': {'show': False, 'x': int(), 'y': int()},
                         'link': {'width': 10, 'bandwidth': 100},
                         'palette': Palette().palette,
                         'node-': {'name': str(), 'label': str(), 'icon': str(), 'x': int(), 'y': int()},
                         'link-': {'node1': str(), 'node2': str(), 'name1': str(), 'name2': str(), 'copy': 0,
                                   'hostname': str(), 'itemin': str(), 'itemout': str(), 'width': int(),
                                   'bandwidth': int()}
                         }
        log.debug('Object singleton ConfigTemplate created')


class ConfigLoader(object):
    def __init__(self, path_cfg: str):

        self.template = ConfigTemplate().template
        self.cfg_dict = {}
        self.obj_nodes = {}
        self.obj_links = {}
        self.zbx = None
        self.load(path_cfg)
        log.debug('Object ConfigLoader created')

    def load(self, path_cfg: str):
        with open(path_cfg, 'r') as stream:
            try:
                self.cfg_dict = yaml3ed.safe_load(stream)
            except yaml3ed.YAMLError as exc:
                print(exc)
        self.check()
        self.zbx = ZabbixAgent(self.cfg_dict['zabbix']['url'], self.cfg_dict['zabbix']['login'],
                               self.cfg_dict['zabbix']['password'])
        log.debug('Config loaded')

    def check(self):
        for cfg_sect in self.template:
            if cfg_sect == 'node-':
                for node in sorted([node for node in self.cfg_dict.keys() if cfg_sect in node]):
                    for cfg_opt in self.template[cfg_sect]:
                        try:
                            self.cfg_dict[node][cfg_opt]
                        except KeyError:
                            if cfg_opt == 'icon':
                                # self.cfg_dict[node][cfg_opt] = str()
                                continue
                            if cfg_opt == 'label':
                                # self.cfg_dict[node][cfg_opt] = str()
                                continue
                            raise ConfigException('The option: {0} is missing in section: [{1}]'
                                                  .format(cfg_sect, cfg_opt))

            if cfg_sect == 'link-':
                for link in sorted([link for link in self.cfg_dict.keys() if cfg_sect in link]):
                    for cfg_opt in self.template[cfg_sect]:
                        try:
                            self.cfg_dict[link][cfg_opt]
                        except KeyError:
                            if cfg_opt == 'copy':
                                # self.cfg_dict[link][cfg_opt] = False
                                continue
                            if cfg_opt == 'width':
                                # self.cfg_dict[link][cfg_opt] = int()
                                continue
                            if cfg_opt == 'bandwidth':
                                # self.cfg_dict[link][cfg_opt] = int()
                                continue
                            raise ConfigException('The option: {0} is missing in section: [{1}]'
                                                  .format(cfg_sect, cfg_opt))

            if cfg_sect == 'palette':
                if len(self.cfg_dict[cfg_sect]) != 9:
                    raise ConfigException('Error in section {0}, number elements not equal 9'.format(cfg_sect))
                continue

            for cfg_opt in self.template[cfg_sect]:
                try:
                    self.cfg_dict[cfg_sect][cfg_opt]
                except KeyError:
                    # if cfg_sect == 'map' and cfg_opt == 'bgcolor':
                    # self.cfg_dict[cfg_sect][cfg_opt] = str()
                    if cfg_sect == 'link-' or cfg_sect == 'node-':
                        continue
                    raise ConfigException('The option: {0} is missing in section: [{1}]'.format(cfg_sect, cfg_opt))
        log.debug('Config check: Ok')

    def create_map(self, font_path_fn: str, icon_path: str):
        self.obj_nodes = {section: None for section in self.cfg_dict if 'node-' in section}
        self.obj_links = {section: None for section in self.cfg_dict if 'link-' in section}
        palette = self.cfg_dict['palette']
        fontsize = int(self.cfg_dict['map']['fontsize'])

        for node in self.obj_nodes.keys():
            x = int(self.cfg_dict[node]['x'])
            y = int(self.cfg_dict[node]['y'])

            if self.cfg_dict[node].get('label'):
                label = self.cfg_dict[node]['label']
            else:
                label = None

            if self.cfg_dict[node].get('icon'):
                icon = self.cfg_dict[node]['icon']
            else:
                icon = None

            self.obj_nodes[node] = (Node(font_path_fn, icon_path, x=x, y=y, label=label, icon=icon, fontsize=fontsize))

        for link in self.obj_links.keys():
            node1 = self.obj_nodes[self.cfg_dict[link]['node1']]
            node2 = self.obj_nodes[self.cfg_dict[link]['node2']]

            if self.cfg_dict[link].get('bandwidth'):
                bandwidth = self.cfg_dict[link]['bandwidth']
            else:
                bandwidth = self.cfg_dict['link']['bandwidth']

            if self.cfg_dict[link].get('width'):
                width = self.cfg_dict[link]['width']
            else:
                width = self.cfg_dict['link']['width']

            self.obj_links[link] = (Link(font_path_fn, node1, node2, bandwidth=bandwidth, width=width,
                                         palette=palette, fontsize=fontsize))

            hostname = self.cfg_dict[link]['hostname']
            item_in = self.cfg_dict[link]['itemin']
            item_out = self.cfg_dict[link]['itemout']

            if hostname and item_in and item_out:
                data_in, data_out = self.zbx.get_item_data2(hostname, item_in, item_out)
                self.obj_links[link].data(in_bps=data_in, out_bps=data_out)
            elif hostname and item_in:
                data_in = self.zbx.get_item_data(hostname, item_in)
                self.obj_links[link].data(in_bps=data_in, out_bps=0)
            elif hostname and item_out:
                data_out = self.zbx.get_item_data(hostname, item_out)
                self.obj_links[link].data(in_bps=0, out_bps=data_out)
            else:
                self.obj_links[link].data(in_bps=0, out_bps=0)

        if int(self.cfg_dict['table']['show']):
            table = Table(font_path_fn, x=int(self.cfg_dict['table']['x']), y=int(self.cfg_dict['table']['y']),
                          palette=palette)
        else:
            table = None

        map_width = int(self.cfg_dict['map']['width'])
        map_height = int(self.cfg_dict['map']['height'])
        if self.cfg_dict['map']['bgcolor']:
            map_bgcolor = self.cfg_dict['map']['bgcolor']
        else:
            map_bgcolor = None
        map_obj = Map(self.obj_links.values(), self.obj_nodes.values(), table=table, len_x=map_width,
                      len_y=map_height, bgcolor=map_bgcolor)
        return map_obj

    def upload(self, img_path_fn: str):
        self.zbx.image_to_zabbix(img_path_fn, self.cfg_dict['map']['name'])


class ConfigCreate(object):
    def __init__(self, map_data: dict, zbx_agent: ZabbixAgent):
        self.zbx = zbx_agent
        self.map_data = map_data
        self.template = ConfigTemplate().template
        self.map_config = {}
        self.dict_call = [self.zbx.get_hostname, self.zbx.get_mapname,
                          self.zbx.get_triggername, self.zbx.get_hostgroupname,
                          self.zbx.get_imagename]
        self.cfg_loader_obj = None
        self.setup_yaml()
        log.debug('Object ConfigCreate created')

    @staticmethod
    def setup_yaml():
        """ StackOverflow Driven Development
        https://stackoverflow.com/a/31609484/4709370
        http://stackoverflow.com/a/8661021 """

        def represent_dict_order(yaml_self, data):
            return yaml_self.represent_mapping('tag:yaml.org,2002:map', data.items())

        yaml3ed.add_representer(OrderedDict, represent_dict_order)

    @staticmethod
    def random_label():
        return ''.join(random.SystemRandom().choice('abcdefgijklmnoprstuvwxyz1234567890') for _ in range(8))

    def create(self):
        elemid_dict = {}
        self.map_config['zabbix'] = {'url': self.zbx.url,
                                     'login': self.zbx.login,
                                     'password': self.zbx.password
                                     }
        self.map_config['map'] = {'name': self.map_data['name'],
                                  'bgcolor': self.template['map']['bgcolor'],
                                  'fontsize': self.template['map']['fontsize'],
                                  'width': int(self.map_data['width']),
                                  'height': int(self.map_data['height'])
                                  }
        self.map_config['table'] = {'show': self.template['table']['show'],
                                    'x': int(self.map_data['width']) - 100,
                                    'y': int(self.map_data['height']) - 300
                                    }

        self.map_config['palette'] = self.template['palette']
        self.map_config['link'] = self.template['link']

        for node in self.map_data['selements']:
            nodeid = node['selementid']

            if int(node['elementtype']) == 4:
                nodename = self.dict_call[int(node['elementtype'])](node['iconid_off'])
            elif int(node['elementtype']) == 3:
                nodename = self.dict_call[int(node['elementtype'])](node['elements'][0]['groupid'])
            elif int(node['elementtype']) == 2:
                nodename = self.dict_call[int(node['elementtype'])](node['elements'][0]['triggerid'])
            elif int(node['elementtype']) == 1:
                nodename = self.dict_call[int(node['elementtype'])](node['elements'][0]['sysmapid'])
            elif int(node['elementtype']) == 0:
                nodename = self.dict_call[int(node['elementtype'])](node['elements'][0]['hostid'])

            elemid_dict[node['selementid']] = nodename

            self.map_config['node-' + nodeid] = {'name': nodename, 'label': str(), 'icon': str()}

            image_b64code = self.zbx.image_get(node['iconid_off'])
            im = Image.open(BytesIO(base64.b64decode(image_b64code)))
            width, height = im.size
            self.map_config['node-' + nodeid] = {
                'name': nodename,
                'x': int(node['x']) + int(width // 2),
                'y': int(node['y']) + int(height // 2)
            }

        for link in self.map_data['links']:
            self.map_config['link-' + link['linkid']] = {'node1': 'node-' + link['selementid2'],
                                                         'node2': 'node-' + link['selementid1'],
                                                         'name1': elemid_dict[link['selementid2']],
                                                         'name2': elemid_dict[link['selementid1']],
                                                         'hostname': str(),
                                                         'itemin': str(),
                                                         'itemout': str()
                                                         }
        del elemid_dict

    @staticmethod
    def _dict_to_orderdict(cfg: dict) -> OrderedDict:
        cfg_order = OrderedDict()
        cfg_templ = OrderedDict([('map', ('name', 'bgcolor', 'fontsize', 'width', 'height')),
                                 ('zabbix', ('url', 'login', 'password')),
                                 ('table', ('show', 'x', 'y')),
                                 ('palette', None),
                                 ('link', ('bandwidth', 'width')),
                                 ('node-', ('name', 'label', 'icon', 'x', 'y')),
                                 ('link-', ('node1', 'node2', 'name1', 'name2', 'copy', 'width', 'bandwidth',
                                            'hostname', 'itemin', 'itemout'))
                                 ])

        for cfg_sect in cfg_templ:

            if cfg_sect == 'node-':
                for node in sorted([node for node in cfg.keys() if cfg_sect in node]):
                    cfg_order[node] = OrderedDict()
                    for cfg_opt in cfg_templ[cfg_sect]:
                        if cfg_opt == 'icon' and cfg_opt not in cfg[node]:
                            continue
                        if cfg_opt == 'label' and cfg_opt not in cfg[node]:
                            continue
                        cfg_order[node][cfg_opt] = cfg[node][cfg_opt]
                continue

            if cfg_sect == 'link-':
                for link in sorted([link for link in cfg.keys() if cfg_sect in link]):
                    cfg_order[link] = OrderedDict()
                    for cfg_opt in cfg_templ[cfg_sect]:
                        if cfg_opt == 'copy' and cfg_opt not in cfg[link]:
                            continue
                        if cfg_opt == 'width' and cfg_opt not in cfg[link]:
                            continue
                        if cfg_opt == 'bandwidth' and cfg_opt not in cfg[link]:
                            continue
                        cfg_order[link][cfg_opt] = cfg[link][cfg_opt]
                continue

            cfg_order[cfg_sect] = OrderedDict()
            if cfg_sect == 'palette':
                cfg_order[cfg_sect] = cfg[cfg_sect]
                continue

            for cfg_opt in cfg_templ[cfg_sect]:
                if cfg_sect == 'map' and cfg_opt == 'bgcolor' and cfg_opt not in cfg[cfg_sect]:
                    continue
                cfg_order[cfg_sect][cfg_opt] = cfg[cfg_sect][cfg_opt]
        return cfg_order

    def save(self, path: str):
        cfg = self._dict_to_orderdict(self.map_config)
        with open(path + '/' + self.map_data['name'] + '.yaml', 'w') as cfg_file:
            try:
                yaml3ed.dump(cfg, cfg_file, explicit_start=True, explicit_end=True,
                             default_flow_style=False, allow_unicode=True, version=(1, 2))
            except yaml3ed.YAMLError as exc:
                print(exc)

    def check_map(self, old_cfg_path: str):
        old_cfg_path_fn = old_cfg_path + '/' + self.map_data['name'] + '.yaml'
        exist = os.path.exists(old_cfg_path_fn)
        if exist:
            self._compare(old_cfg_path_fn)

    def _compare(self, old_cfg_path_file: str):

        self.cfg_loader_obj = ConfigLoader(old_cfg_path_file)
        config_old = self.cfg_loader_obj.cfg_dict

        for section in [sect for sect in self.template.keys()
                        if sect != 'zabbix' and sect != 'map' and sect != 'node-' and sect != 'link-']:

            if section == 'palette':
                self.map_config[section] = config_old[section]
                continue

            for option in self.template[section]:
                self.map_config[section][option] = config_old[section][option]

        for option in self.template['map']:
            if option in ['bgcolor', 'fontsize']:
                self.map_config['map'][option] = config_old['map'][option]

        for section in self.map_config:
            if 'node-' in section:
                if config_old.get(section):
                    if config_old[section].get('label'):
                        self.map_config[section]['label'] = config_old[section]['label']
                    if config_old[section].get('icon'):
                        self.map_config[section]['icon'] = config_old[section]['icon']
            if 'link-' in section:
                if config_old.get(section):
                    self.map_config[section]['hostname'] = config_old[section]['hostname']
                    self.map_config[section]['itemin'] = config_old[section]['itemin']
                    self.map_config[section]['itemout'] = config_old[section]['itemout']
                    if config_old[section].get('width'):
                        self.map_config[section]['width'] = config_old[section]['width']
                    if config_old[section].get('bandwidth'):
                        self.map_config[section]['bandwidth'] = config_old[section]['bandwidth']

        for section in [link for link in config_old.keys() if 'link-' in link]:

            if config_old[section].get('copy'):
                new_section = 'link-' + self.random_label()
                node1_sect = config_old[section]['node1']
                node2_sect = config_old[section]['node2']
                node1_new_sect = 'node-' + self.random_label()
                node2_new_sect = 'node-' + self.random_label()

                self.map_config.update({new_section: dict()})
                for option in config_old[section]:
                    if 'node1' in option:
                        self.map_config[new_section][option] = node1_new_sect
                    elif 'node2' in option:
                        self.map_config[new_section][option] = node2_new_sect
                    else:
                        self.map_config[new_section][option] = config_old[section][option]

                self.map_config.update({node1_new_sect: dict()})
                self.map_config.update({node2_new_sect: dict()})
                for option in config_old[node1_sect]:
                    self.map_config[node1_new_sect][option] = config_old[node1_sect][option]
                for option in config_old[node2_sect]:
                    self.map_config[node2_new_sect][option] = config_old[node2_sect][option]
