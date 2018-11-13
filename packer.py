# coding: utf-8
import os, sys
import datetime, time
import hashlib
import subprocess
import shutil
import re
import pprint

def run(cmd):
    print cmd 
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE) 
    p.wait()
    code = p.returncode
    data = p.stdout.read()
    return code, data

def md5sum(filename):
    m = hashlib.md5()
    with open(filename) as f:
        m.update(f.read())
    return m.hexdigest()

def md5str(s):
    m = hashlib.md5()
    m.update(s)
    return m.hexdigest()


def get_files(fromdir, todir):
    allfiles = {'html':[], 'js':[], 'css':[], 'sass':[], 'image':[]}

    for root,dirs,files in os.walk(fromdir):
        for fn in files:
            key = ''
            if fn.endswith(('.html', '.js', '.css')):
                key = fn.split('.')[-1]
            elif fn.endswith(('.sass', '.scss')):
                key = 'sass'
            elif fn.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico')):
                key = 'image'

            if not key:
                continue
                
            fpath = os.path.join(root, fn)

            if fpath.startswith(todir):
                continue

            allfiles[key].append(fpath)

    print 'found files:'
    pprint.pprint(allfiles)
    print

    return allfiles


def copy_file(frompath, topath, filemd5=True):
    dirname = os.path.dirname(topath)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    shutil.copyfile(frompath, topath)
    k = topath.split('.')[-1]
    val = md5sum(topath)
    filename  = os.path.basename(topath)
    filename2 = filename[:(len(k)+1)*-1] + ".%s.%s" % (val[-8:], k)

    if filemd5:
        topath2 = os.path.join(os.path.dirname(topath), filename2)
        print 'copy:', topath2
        os.rename(topath, topath2)
    else:
        print 'copy:', topath

    return filename, filename2


def html_replace(out, tofiles, tpl='css'):
    jstpl  = '<script type="text/javascript" src="%s"></script>\n'
    csstpl = '<link href="%s" rel="stylesheet">\n'

    ret = re.search('\<\!\-\-css:([a-zA-Z0-9\/\.\,]+)\-\-\>', out)
    ret2 = re.search('\<\!\-\-css\-\-\>', out)
    if ret:
        items = ret.groups()[0].split(',')
        s = ''.join([ csstpl % (tofiles[x]) for x in items ])
        out = out.replace(ret.group(), s)
    elif ret2:
        items = [ x for x in tofiles.keys() if x.endswith('.css')]
        s = ''.join([ csstpl % (tofiles[x]) for x in items ])
        out = out.replace(ret2.group(), s)

    return out

def main():
    fromdir = os.path.abspath(sys.argv[1])
    todir   = os.path.abspath(sys.argv[2])


    files = get_files(fromdir, todir)

    # apply sass to css
    for fn in files['sass']:
        topath = os.path.join(todir, fn[len(fromdir)+1:])
        topath = topath[:-4] + 'css'
        #print topath
        
        dirname = os.path.dirname(topath)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
   
        cmd = "sass %s %s" % (fn, topath)
        run(cmd) 
       
        val = md5sum(topath)

        topath2 = topath[:-4] + ".%s.css" % (val[-8:])
        print 'copy:', topath2
        os.rename(topath, topath2)
        
        mapfile = topath + '.map'
        if os.path.isfile(mapfile):
            os.rename(mapfile, topath2+'.map')

    # copy css/js/image
    tofiles = {}
    for k in ['css', 'js', 'image']:
        for fn in files[k]:
            topath = os.path.join(todir, fn[len(fromdir)+1:])
            if k == 'image' and topath.endswith('.ico'):
                copy_file(fn, os.path.join(todir, os.path.basename(fn)), False)
                continue

            filename, filename2 = copy_file(fn, topath)
            if k in ('css', 'js'):
                tofiles[k+'/'+filename] = k+'/'+filename2

    # create html
    for fn in files['html']:
        out = ''
        with open(fn) as f:
            out = f.read() 
        out = html_replace(out, tofiles, 'css')
        out = html_replace(out, tofiles, 'js')

        topath = os.path.join(todir, os.path.basename(fn))
        dirname = os.path.dirname(topath)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        with open(topath, 'w+') as f:
            f.write(out)
        print 'create:', topath

if __name__ == '__main__':
    main()
    print 'success!'


