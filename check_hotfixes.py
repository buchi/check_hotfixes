#!/bin/env python
#
# Check Plone installations for hotfixes.
# Command to download and run this script:
# python -c "import urllib; exec urllib.urlopen('https://raw.github.com/buchi/check_hotfixes/master/check_hotfixes.py').read()"

import subprocess
import os.path
import re


def locate_instances():
    process = subprocess.Popen(['locate', 'bin/instance'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    if process.returncode == 0:
        return [line for line in out.split('\n') if line.strip()]

def locate_zopectl():
    process = subprocess.Popen(['locate', '*/bin/zopectl'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    if process.returncode == 0:
        return [line for line in out.split('\n') if line.strip()]

def search_egg(name, instance):
    """If an egg with the given name is found return it's version."""
    version_pattern = re.compile(r'%s-(.*)-py\d\.\d.egg' % name)

    if os.path.exists(instance):
        for line in open(instance, 'rb'):
            if '/%s-' % name in line:
                match = version_pattern.search(line)
                if match:
                    return match.group(1)
                else:
                    return 'UNKNOWN VERSION'

        if 'import site' in open(instance, 'rb').read():
            site = os.path.join(os.path.dirname(instance), '../parts', os.path.basename(instance), 'site.py')
            if os.path.exists(site):
                for line in open(site, 'rb'):
                    if '/%s-' % name in line:
                        match = version_pattern.search(line)
                        if match:
                            return match.group(1)
                        else:
                            return 'UNKNOWN VERSION'
    return None


zope_conf_pattern = re.compile(r'/[^\"\']*zope.conf')
def search_zope_conf(instance):
    if os.path.exists(instance):
        for line in open(instance, 'rb'):
            if 'etc/zope.conf' in line:
                match = zope_conf_pattern.search(line)
                if match:
                    return match.group(0)
    return None

products_pattern = re.compile(r'products ')
def search_product(name, zope_conf):
    # Get product folders from zope.conf
    product_folders = []
    if os.path.exists(zope_conf):
        for line in open(zope_conf, 'rb'):
            if line.lstrip().startswith('products'):
                product_line = line.strip().split()
                if len(product_line) > 1:
                    product_folders.append(product_line[1])

    # Scan product folders for product
    if name == 'Plone':
        name = 'CMFPlone'
    if name.startswith('Products.'):
        name = name[9:]
    
    for folder in product_folders:
        if os.path.isdir(folder):
            for item in os.listdir(folder):
                if item == name:
                    version = read_product_version(os.path.join(folder, item))
                    return version
    return None

def read_product_version(product):
    version = '0.0'
    version_file = os.path.join(product, 'version.txt')
    if os.path.exists(version_file):
        version = open(version_file, 'rb').read().strip()
    return version

def main():
    instances = locate_instances()
    for instance in instances:
        plone_version = search_egg('Plone', instance)
        zope_conf = search_zope_conf(instance)

        if plone_version is None and zope_conf is not None:
            plone_version = search_product('Plone', zope_conf)
            
        if plone_version is None:
            print "%s: No Plone installation detected." % instance
            continue
        print "%s: Plone %s" % (instance, plone_version)

        for hotfix, versions in HOTFIXES.items():
            for version in versions:
                iversion = search_egg(version[0], instance)
                if iversion is None:
                    iversion = search_product(version[0], zope_conf)
                if iversion is None:
                    continue
                if (NormalizedVersion(iversion) >= NormalizedVersion(version[1]) and 
                    NormalizedVersion(iversion) <= NormalizedVersion(version[2])):
                    installed = search_egg(hotfix[0], instance)
                    if installed is None:
                        installed = search_product(hotfix[0], zope_conf)
                    if installed is None:
                        print "%s ***** MISSING *****" % hotfix[0]
                    elif installed == '0.0':
                        print "%s unkown version installed." % hotfix[0]
                    elif NormalizedVersion(installed)<NormalizedVersion(hotfix[1]):
                        print "%s %s ***** needs update to %s *****" % (hotfix[0], installed, hotfix[1])
                    else:
                        print "%s %s ok." % (hotfix[0], installed)
                

HOTFIXES = {
    ('Products.PloneHotfix20121106', '1.2'): [('Plone', '2.0', '4.2.2')],
    ('Products.PloneHotfix20110928', '1.0'): [('Plone', '4.0a1', '4.0.9'), ('Plone', '4.1a1', '4.1'), ('Plone', '4.2a1', '4.2a2')],
    ('Products.PloneHotfix20110720', '1.0'): [('Plone', '2.0', '4.0.3')],
    ('Products.PloneHotfix20110531', '2.0'): [('Plone', '3.0', '4.0.6'), ('Plone', '4.1a1', '4.1rc3')],
    ('Products.Zope_Hotfix_20111024', '1.0'): [('Plone', '4.0a1', '4.1.3'), ('Plone', '4.2a1', '4.2b1')],
    ('Products.Zope_Hotfix_CVE_2010_1104', '1.0'): [('Plone', '2.1', '3.3.2'), ('Plone', '4.0a1', '4.0a3')],
    ('Products.Zope_Hotfix_20110622', '1.0'): [('Plone', '3.0', '3.3.5'), ('Plone', '4.0a1', '4.0.7'), ('Plone', '4.1a1', '4.1rc3')],
    ('Products.PloneFormGen', '1.7.11'): [('Products.PloneFormGen', '1.7.4', '1.7.8')],
    ('Products.PloneFormGen', '1.6.7'): [('Products.PloneFormGen', '1.6.0b1', '1.6.6')],
}

# Version number parsing and comparison
FINAL_MARKER = ('f',)
VERSION_RE = re.compile(r'''
    ^
    (?P<version>\d+\.\d+)          # minimum 'N.N'
    (?P<extraversion>(?:\.\d+)*)   # any number of extra '.N' segments
    (?:
        (?P<prerel>[abc]|rc)       # 'a'=alpha, 'b'=beta, 'c'=release candidate
                                   # 'rc'= alias for release candidate
        (?P<prerelversion>\d+(?:\.\d+)*)
    )?
    (?P<postdev>(\.post(?P<post>\d+))?(\.dev(?P<dev>\d+))?)?
    $''', re.VERBOSE)


class NormalizedVersion(object):
    """A rational version."""

    def __init__(self, s):
        """Create a NormalizedVersion instance from a version string."""
        self._parse(s)

    def _parse(self, s):
        """Parses a string version into parts."""
        match = VERSION_RE.search(s)
        if not match:
            raise ValueError("invalid version number '%s'" % s)

        groups = match.groupdict()
        parts = []

        # main version
        block = self._parse_numdots(groups['version'], s, False, 2)
        extraversion = groups.get('extraversion')
        if extraversion not in ('', None):
            block += self._parse_numdots(extraversion[1:], s)
        parts.append(tuple(block))

        # prerelease
        prerel = groups.get('prerel')
        if prerel is not None:
            block = [prerel]
            block += self._parse_numdots(groups.get('prerelversion'), s,
                                         pad_zeros_length=1)
            parts.append(tuple(block))
        else:
            parts.append(FINAL_MARKER)

        # postdev
        if groups.get('postdev'):
            post = groups.get('post')
            dev = groups.get('dev')
            postdev = []
            if post is not None:
                postdev.extend([FINAL_MARKER[0], 'post', int(post)])
                if dev is None:
                    postdev.append(FINAL_MARKER[0])
            if dev is not None:
                postdev.extend(['dev', int(dev)])
            parts.append(tuple(postdev))
        else:
            parts.append(FINAL_MARKER)
        self.parts = tuple(parts)

    def _parse_numdots(self, s, full_ver_str, drop_trailing_zeros=True,
                       pad_zeros_length=0):
        """Parse 'N.N.N' sequences, return a list of ints."""
        nums = []
        for n in s.split("."):
            if len(n) > 1 and n[0] == '0':
                raise ValueError("cannot have leading zero in "
                    "version number segment: '%s' in %r" % (n, full_ver_str))
            nums.append(int(n))
        if drop_trailing_zeros:
            while nums and nums[-1] == 0:
                nums.pop()
        while len(nums) < pad_zeros_length:
            nums.append(0)
        return nums

    def __str__(self):
        return self.parts_to_str(self.parts)

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, self)

    def _cannot_compare(self, other):
        raise TypeError("cannot compare %s and %s"
                % (type(self).__name__, type(other).__name__))

    def __eq__(self, other):
        if not isinstance(other, NormalizedVersion):
            self._cannot_compare(other)
        return self.parts == other.parts

    def __lt__(self, other):
        if not isinstance(other, NormalizedVersion):
            self._cannot_compare(other)
        return self.parts < other.parts

    def __ne__(self, other):
        return not self.__eq__(other)

    def __gt__(self, other):
        return not (self.__lt__(other) or self.__eq__(other))

    def __le__(self, other):
        return self.__eq__(other) or self.__lt__(other)

    def __ge__(self, other):
        return self.__eq__(other) or self.__gt__(other)


if __name__ == "__main__":
    main()
