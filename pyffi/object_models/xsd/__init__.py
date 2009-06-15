"""This module provides a base class and a metaclass for parsing an XSD
schema and providing an interface for writing XML files that follow this
schema.
"""

# ***** BEGIN LICENSE BLOCK *****
#
# Copyright (c) 2007-2009, Python File Format Interface
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#
#    * Neither the name of the Python File Format Interface
#      project nor the names of its contributors may be used to endorse
#      or promote products derived from this software without specific
#      prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# ***** END LICENSE BLOCK *****

import logging
import time
import xml.etree.cElementTree

import pyffi.object_models

class NodeTree:
    """Converts an xsd element tree into a tree of nodes that contain all
    methods for creating classes. Each node has a class matching the
    element type.
    """
    logger = logging.getLogger("pyffi.object_models.xsd")

    class Node(object):
        def __init__(self, element, parent=None):
            # XXX not needed for now
            #self.element = element
            #self.parent = weakref.ref(parent) if parent else None

            # create class instances for all children
            self.children = [NodeTree.factory(child, self)
                             for child in element.getchildren()]

    class All(Node):
        pass

    class Annotation(Node):
        pass

    class Any(Node):
        pass

    class AnyAttribute(Node):
        pass

    class Appinfo(Node):
        pass

    class Attribute(Node):
        pass

    class AttributeGroup(Node):
        pass

    class Choice(Node):
        pass

    class ComplexContent(Node):
        pass

    class ComplexType(Node):
        pass

    class Documentation(Node):
        pass

    class Element(Node):
        pass

    class Enumeration(Node):
        pass

    class Extension(Node):
        pass

    class Field(Node):
        pass

    class Group(Node):
        pass

    class Import(Node):
        pass

    class Include(Node):
        pass

    class Key(Node):
        pass

    class Keyref(Node):
        pass

    class Length(Node):
        pass

    class List(Node):
        pass

    class MaxExclusive(Node):
        pass

    class MaxInclusive(Node):
        pass

    class MaxLength(Node):
        pass

    class MinInclusive(Node):
        pass

    class MinLength(Node):
        pass

    class Pattern(Node):
        pass

    class Redefine(Node):
        pass

    class Restriction(Node):
        pass

    class Schema(Node):
        pass

    class Selector(Node):
        pass

    class Sequence(Node):
        pass

    class SimpleContent(Node):
        pass

    class SimpleType(Node):
        pass

    class Union(Node):
        pass

    class Unique(Node):
        pass

    def __init__(self, root_element):
        self.root = self.factory(root_element)

    @classmethod
    def factory(cls, element, parent=None):
        """Create an appropriate instance for the given xsd element."""
        # get last part of the tag
        class_name = element.tag.split("}")[-1]
        class_name = class_name[0].upper() + class_name[1:]
        try:
            #cls.logger.debug("Creating %s instance for %s."
            #                 % (class_name, xsd_element))
            return getattr(cls, class_name)(element, parent)
        except AttributeError:
            cls.logger.warn("Unknown element type: making node class %s."
                            % class_name)
            class_ = type(class_name, (cls.Node,), {})
            setattr(cls, class_name, class_)
            return class_(element, parent)


class MetaFileFormat(pyffi.object_models.MetaFileFormat):
    """The MetaFileFormat metaclass transforms the XSD description of a
    xml format into a bunch of classes which can be directly used to
    manipulate files in this format.

    The actual implementation of the parser is delegated to
    L{XsdSaxHandler}.
    """

    def __init__(cls, name, bases, dct):
        """This function constitutes the core of the class generation
        process. For instance, we declare DaeFormat to have metaclass
        MetaFileFormat, so upon creation of the DaeFormat class,
        the __init__ function is called, with

        :param cls: The class created using MetaFileFormat, for example
            DaeFormat.
        :param name: The name of the class, for example 'DaeFormat'.
        :param bases: The base classes, usually (object,).
        :param dct: A dictionary of class attributes, such as 'xsdFileName'.
        """
        super(MetaFileFormat, cls).__init__(name, bases, dct)

        # open XSD file
        xsdfilename = dct.get('xsdFileName')
        if xsdfilename:
            # open XSD file
            xsdfile = cls.openfile(xsdfilename, cls.xsdFilePath)

            # parse the XSD file: control is now passed on to NodeTree
            # which takes care of the class creation
            cls.logger.debug("Parsing %s and generating classes." % xsdfilename)
            start = time.clock()
            try:
                tree = NodeTree(xml.etree.cElementTree.parse(xsdfile).getroot())
            finally:
                xsdfile.close()
            cls.logger.debug("Parsing finished in %.3f seconds." % (time.clock() - start))

class FileFormat(pyffi.object_models.FileFormat):
    """This class can be used as a base class for file formats. It implements
    a number of useful functions such as walking over directory trees and a
    default attribute naming function.
    """
    __metaclass__ = MetaFileFormat
    xsdFileName = None #: Override.
    xsdFilePath = None #: Override.
    logger = logging.getLogger("pyffi.object_models.xsd")

    @staticmethod
    def name_attribute(name):
        """Converts an attribute name, as in the xsd file, into a name usable
        by python.

        :param name: The attribute name.
        :type name: str
        :return: Reformatted attribute name, useable by python.

        >>> FileFormat.name_attribute('tHis is A Silly naME')
        'this_is_a_silly_name'
        """

        # str(name) converts name to string in case name is a unicode string
        parts = str(name).replace(":", "_").split()
        return "_".join(part.lower() for part in parts)

    @staticmethod
    def name_class(name):
        """Converts a class name, as in the xsd file, into a name usable
        by python.

        :param name: The class name.
        :type name: str
        :return: Reformatted class name, useable by python.

        >>> FileFormat.name_class('this IS a sillyNAME')
        'ThisISASillyNAME'
        """

        # str(name) converts name to string in case name is a unicode string
        partss = [part.split("_") for part in str(name).split()]
        attrname = ""
        for parts in partss:
            for part in parts:
                attrname += part[0].upper() + part[1:]
        return attrname

class XsdSaxHandler:
    """Scheduled for deletion."""
    # xsd elements
    # (see http://www.w3.org/TR/xmlschema-0/#indexEl)
    # xsd attributes
    # (see http://www.w3.org/TR/xmlschema-0/#indexAttr)
    attrAbstract = 1
    attrAttributeFormDefault = 2
    attrBase = 3
    attrBlock = 4
    attrBlockDefault = 5
    attrDefault = 6
    attrElementFormDefault = 7
    attrFinal = 8
    attrFinalDefault = 9
    attrFixed = 10
    attrForm = 11
    attrItemType = 12
    attrMemberTypes = 13
    attrMaxOccurs = 14
    attrMinOccurs = 15
    attrMixed = 16
    attrName = 17
    attrNamespace = 18
    attrXsiNoNamespaceSchemaLocation = 19
    attrXsiNil = 20
    attrNillable = 21
    attrProcessContents = 22
    attrRef = 23
    attrSchemaLocation = 24
    attrXsiSchemaLocation = 25
    attrSubstitutionGroup = 26
    attrTargetNamespace = 27
    attrType = 28
    attrXsiType = 29
    attrUse = 30
    attrXpath = 31

    attrs = {
        "abstract": attrAbstract,
        "attributeFormDefault": attrAttributeFormDefault,
        "base": attrBase,
        "block": attrBlock,
        "blockDefault": attrBlockDefault,
        "default": attrDefault,
        "elementFormDefault": attrElementFormDefault,
        "final": attrFinal,
        "finalDefault": attrFinalDefault,
        "fixed": attrFixed,
        "form": attrForm,
        "itemType": attrItemType,
        "memberTypes": attrMemberTypes,
        "maxOccurs": attrMaxOccurs,
        "minOccurs": attrMinOccurs,
        "mixed": attrMixed,
        "name": attrName,
        "namespace": attrNamespace,
        "xsi:noNamespaceSchemaLocation": attrXsiNoNamespaceSchemaLocation,
        "xsi:nil": attrXsiNil,
        "nillable": attrNillable,
        "processContents": attrProcessContents,
        "ref": attrRef,
        "schemaLocation": attrSchemaLocation,
        "xsi:schemaLocation": attrXsiSchemaLocation,
        "substitutionGroup": attrSubstitutionGroup,
        "targetNamespace": attrTargetNamespace,
        "type": attrType,
        "xsi:type": attrXsiType,
        "use": attrUse,
        "xpath": attrXpath}
