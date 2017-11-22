#!/usr/bin/env python3
from xml.etree.ElementTree import Element, SubElement, Comment, ElementTree
import numpy as np
from math import pi, atan2, sqrt

# Denavit Hartenberg to URDF converter


def DHMat(theta, d, a, alpha):
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)
    cos_alpha = np.cos(alpha)
    sin_alpha = np.sin(alpha)

    return np.matrix([
        [cos_theta, -sin_theta * cos_alpha,
         sin_theta * sin_alpha, a * cos_theta],
        [sin_theta, cos_theta * cos_alpha,
         -cos_theta * sin_alpha, a * sin_theta],
        [0, sin_alpha, cos_alpha, d],
        [0, 0, 0, 1],
    ])


def homo2euler(Homo):
    r = atan2(Homo[2, 1], Homo[2, 2])
    p = atan2(-Homo[2, 0], sqrt(Homo[2, 1]**2 + Homo[2, 2]**2))
    w = atan2(Homo[1, 0], Homo[0, 0])
    x = Homo[0, 3]
    y = Homo[1, 3]
    z = Homo[2, 3]
    return (" ".join([str(x), str(y), str(z)]), " ".join([str(r), str(p), str(w)]))


class URDF(object):

    def __init__(self, name):
        self.name = name
        self.robot = Element(
            'robot', {'name': self.name, 'xmlns:xacro': 'http://www.ros.org/wiki/xacro'})
        self.comment(self.robot, "Uthai Humanoid, FIBO, KMUTT, Thailand, 2017")
        self.comment(self.robot, "This file generated by Liews Wuttipat")

    def addProps(self, props):
        for prop in props:
            SubElement(self.robot, 'xacro:property', {
                       'name': prop[0], 'value': prop[1]})

    @staticmethod
    def Link(name, stl=None):
        link = Element('link', {'name': name})
        if stl != None:
            visual = SubElement(link, 'visual')
            geometry = SubElement(visual, 'geometry')
            SubElement(
                geometry, 'mesh', {'filename': "package://uthai_description/meshes/" + stl})
            collision = SubElement(link, 'collision')
            geometry = SubElement(collision, 'geometry')
            SubElement(
                geometry, 'mesh', {'filename': "package://uthai_description/meshes/" + stl})
        return link

    @staticmethod
    def Joint(name, jtype, parent, child, xyz=None, rpy=None, axis="0 0 1", limit=None):
        joint = Element('joint', {'name': name, 'type': jtype})
        SubElement(joint, 'parent', {'link': parent})
        SubElement(joint, 'child', {'link': child})
        if (xyz != None) and (rpy != None):
            SubElement(joint, 'origin', {'xyz': xyz, 'rpy': rpy})
        if jtype == 'revolute':
            SubElement(joint, 'axis', {'xyz': axis})
            if limit is None:
                defaut_limit = {
                    'effort': '10',
                    'lower': '-2.6179939',
                    'upper': '2.6179939',
                    'velocity': '5.6548668'
                }
                SubElement(joint, 'limit', defaut_limit)
            else:
                SubElement(joint, 'limit', limit)
        return joint

    def addLink(self, name, stl=None):
        self.robot.append(self.Link(name, stl))

    def addJoint(self, name, jtype, parent, child, xyz=None, rpy=None, axis="0 0 1", limit=None):
        self.robot.append(
            self.Joint(name, jtype, parent, child, xyz, rpy, axis, limit))

    @staticmethod
    def Macro(name, params):
        macro = Element('macro', {'name': name, 'params': params})
        return macro

    @staticmethod
    def comment(element, text):
        element.append(Comment(text))

    def write(self):
        ElementTree(self.robot).write(
            "uthai_utils/DH2URDF/" + self.name + ".xacro")


class DH2URDF(object):

    def __init__(self, name, filename):
        self.urdf = URDF(name)
        self.DH_fixed_macro()
        self.DH_F_macro()
        self.DH_R_macro()
        self.urdf.comment(self.urdf.robot, "End Macro to make dummy link")
        self.num_joint = [1, 1]
        self.urdf.addLink('base_link')
        self.urdf.addLink('fd_base_link')
        self.urdf.addJoint('fixed_fd', 'fixed', 'base_link', 'fd_base_link')
        print("======================================")
        print("Generating...........Loading Parameter")
        print("======================================")
        with open(filename, 'r') as data_file:
            dh_file = data_file.read().split('\n\n')
            dh_props = dh_file[0].split('\n')
            for dh_prop in dh_props:
                exec(dh_prop)
                print(dh_prop)
            print("")
            print("======================================")
            print("Generating......Calculate DH Parameter")
            print("======================================")
            dh_tables = dh_file[2:]
            for dh_table in dh_tables:
                dh_datas = []
                for dhs in dh_table.split('\n'):
                    dh = dhs.split('|')
                    dh_datas.append([dh[0].split(','), dh[1]])

                for i, dhs in enumerate(dh_datas):
                    tf = eval('homo2euler(DHMat(' + dhs[1] + '))')
                    dh_data = {
                        'type': 'F' if (i + 1) == len(dh_datas) else dh_datas[i + 1][0][2],
                        'xyz': tf[0],
                        'rpy': tf[1],
                        'parent': dhs[0][0],
                        'child': dhs[0][1]
                    }
                    self.DH_macro(dh_data)
                    print(dh_data)

                print("")
        print("======================================")
        print("Generate URDF From DH Table Complete..")
        print("======================================\n")
        self.urdf.write()

    def DH_macro(self, dh):
        if dh['type'] == 'F':
            del dh['type']
            dh['id'] = str(self.num_joint[1])
            self.num_joint[1] += 1
            self.urdf.robot.append(Element('DH_F', dh))
        elif dh['type'] == 'R':
            del dh['type']
            dh['id'] = str(self.num_joint[0])
            self.num_joint[0] += 1
            self.urdf.robot.append(Element('DH_R', dh))

    def DH_fixed_macro(self):
        macro = self.urdf.Macro('DH_fixed', 'parent child xyz rpy')
        joint = self.urdf.Joint(
            'jd_${child}', 'fixed', 'fd_${parent}', 'f_${child}', '${xyz}', '${rpy}')
        macro.append(joint)
        link = self.urdf.Link('f_${child}')
        macro.append(link)
        link = self.urdf.Link('fd_${child}')
        macro.append(link)
        self.urdf.robot.append(macro)

    def DH_F_macro(self):
        macro = self.urdf.Macro('DH_F', 'parent child xyz rpy id')
        data = {
            'parent': '${parent}',
            'child': '${child}',
            'xyz': '${xyz}',
            'rpy': '${rpy}'
        }
        macro.append(Element('DH_fixed', data))
        joint = self.urdf.Joint(
            'jf_${id}', 'fixed', 'f_${child}', 'fd_${child}')
        macro.append(joint)
        self.urdf.robot.append(macro)

    def DH_R_macro(self):
        macro = self.urdf.Macro('DH_R', 'parent child xyz rpy id')
        data = {
            'parent': '${parent}',
            'child': '${child}',
            'xyz': '${xyz}',
            'rpy': '${rpy}'
        }
        macro.append(Element('DH_fixed', data))
        joint = self.urdf.Joint(
            'j_${id}', 'revolute', 'f_${child}', 'fd_${child}')
        macro.append(joint)
        self.urdf.robot.append(macro)


if __name__ == '__main__':
    DH2URDF('myRobot', 'uthai_utils/DH2URDF/dh_param_file_uthai.ldh')
