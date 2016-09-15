#!/usr/bin/env python

# Copyright (c) 2007, 2008 Rocco Rutte <pdmef@gmx.net> and others.
# License: MIT <http://www.opensource.org/licenses/mit-license.php>
from __future__ import absolute_import, print_function

import sys
import os
import re
from optparse import OptionParser

from mercurial import node

from .hg2git import (
    fixup_user,
    get_branch,
    get_changeset,
    get_git_sha1,
    load_cache,
    save_cache,
    set_default_branch,
    set_origin_name,
    setup_repo,
    CacheFile,
)


if sys.platform == "win32":
  # On Windows, sys.stdout is initially opened in text mode, which means that
  # when a LF (\n) character is written to sys.stdout, it will be converted
  # into CRLF (\r\n).  That makes git blow up, so use this platform-specific
  # code to change the mode of sys.stdout to binary.
  import msvcrt
  # msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

# silly regex to catch Signed-off-by lines in log message
sob_re=re.compile('^Signed-[Oo]ff-[Bb]y: (.+)$')
# insert 'checkpoint' command after this many commits or none at all if 0
cfg_checkpoint_count=0
# write some progress message every this many file contents written
cfg_export_boundary=1000

def gitmode(flags):
  return 'l' in flags and '120000' or 'x' in flags and '100755' or '100644'

def wr_no_nl(msg=''):
  if msg:
    sys.stdout.write(msg)

def wr(msg=''):
  wr_no_nl(msg)
  sys.stdout.write('\n')
  #map(lambda x: sys.stderr.write('\t[%s]\n' % x),msg.split('\n'))

def checkpoint(count):
  count=count+1
  if cfg_checkpoint_count>0 and count%cfg_checkpoint_count==0:
    sys.stderr.write("Checkpoint after %d commits\n" % count)
    wr('checkpoint')
    wr()
  return count

def revnum_to_revref(rev, old_marks):
  """Convert an hg revnum to a git-fast-import rev reference (an SHA1
  or a mark)"""
  return old_marks.get(rev) or ':%d' % (rev+1)

def file_mismatch(f1,f2):
  """See if two revisions of a file are not equal."""
  return node.hex(f1)!=node.hex(f2)

def split_dict(dleft,dright,l=[],c=[],r=[],match=file_mismatch):
  """Loop over our repository and find all changed and missing files."""
  for left in dleft.keys():
    right=dright.get(left,None)
    if right==None:
      # we have the file but our parent hasn't: add to left set
      l.append(left)
    elif match(dleft[left],right) or gitmode(dleft.flags(left))!=gitmode(dright.flags(left)):
      # we have it but checksums mismatch: add to center set
      c.append(left)
  for right in dright.keys():
    left=dleft.get(right,None)
    if left==None:
      # if parent has file but we don't: add to right set
      r.append(right)
    # change is already handled when comparing child against parent
  return l,c,r

def get_filechanges(repo,revision,parents,mleft):
  """Given some repository and revision, find all changed/deleted files."""
  l,c,r=[],[],[]
  for p in parents:
    if p<0: continue
    mright=repo.changectx(p).manifest()
    l,c,r=split_dict(mleft,mright,l,c,r)
  l.sort()
  c.sort()
  r.sort()
  return l,c,r

def get_author(logmessage,committer,authors):
  """As git distincts between author and committer of a patch, try to
  extract author by detecting Signed-off-by lines.

  This walks from the end of the log message towards the top skipping
  empty lines. Upon the first non-empty line, it walks all Signed-off-by
  lines upwards to find the first one. For that (if found), it extracts
  authorship information the usual way (authors table, cleaning, etc.)

  If no Signed-off-by line is found, this defaults to the committer.

  This may sound stupid (and it somehow is), but in log messages we
  accidentially may have lines in the middle starting with
  "Signed-off-by: foo" and thus matching our detection regex. Prevent
  that."""

  loglines=logmessage.split('\n')
  i=len(loglines)
  # from tail walk to top skipping empty lines
  while i>=0:
    i-=1
    if len(loglines[i].strip())==0: continue
    break
  if i>=0:
    # walk further upwards to find first sob line, store in 'first'
    first=None
    while i>=0:
      m=sob_re.match(loglines[i])
      if m==None: break
      first=m
      i-=1
    # if the last non-empty line matches our Signed-Off-by regex: extract username
    if first!=None:
      r=fixup_user(first.group(1),authors)
      return r
  return committer

def export_file_contents(ctx,manifest,files,hgtags,encoding=''):
  count=0
  max=len(files)
  for file in files:
    # Skip .hgtags files. They only get us in trouble.
    if not hgtags and file == ".hgtags":
      sys.stderr.write('Skip %s\n' % (file))
      continue
    d=ctx.filectx(file).data()
    if encoding:
      filename=file.decode(encoding).encode('utf8')
    else:
      filename=file
    wr('M %s inline %s' % (gitmode(manifest.flags(file)),
                           strip_leading_slash(filename)))
    wr('data %d' % len(d)) # had some trouble with size()
    wr(d)
    count+=1
    if count%cfg_export_boundary==0:
      sys.stderr.write('Exported %d/%d files\n' % (count,max))
  if max>cfg_export_boundary:
    sys.stderr.write('Exported %d/%d files\n' % (count,max))

def sanitize_name(name,what="branch", mapping={}):
  """Sanitize input roughly according to git-check-ref-format(1)"""

  # NOTE: Do not update this transform to work around
  # incompatibilities on your platform. If you change it and it starts
  # modifying names which previously were not touched it will break
  # preexisting setups which are doing incremental imports.
  #
  # Use the -B and -T options to mangle branch and tag names
  # instead. If you have a source repository where this is too much
  # work to do manually, write a tool that does it for you.

  def dot(name):
    if name[0] == '.': return '_'+name[1:]
    return name

  n=mapping.get(name,name)
  p=re.compile('([[ ~^:?\\\\*]|\.\.)')
  n=p.sub('_', n)
  if n[-1] in ('/', '.'): n=n[:-1]+'_'
  n='/'.join(map(dot,n.split('/')))
  p=re.compile('_+')
  n=p.sub('_', n)

  if n!=name:
    sys.stderr.write('Warning: sanitized %s [%s] to [%s]\n' % (what,name,n))
  return n

def strip_leading_slash(filename):
  if filename[0] == '/':
    return filename[1:]
  return filename

def export_commit(ui,repo,revision,old_marks,max,count,authors,
                  branchesmap,sob,brmap,hgtags,encoding='',fn_encoding=''):
  def get_branchname(name):
    if brmap.has_key(name):
      return brmap[name]
    n=sanitize_name(name, "branch", branchesmap)
    brmap[name]=n
    return n

  (revnode,_,user,(time,timezone),files,desc,branch,_)=get_changeset(ui,repo,revision,authors,encoding)

  branch=get_branchname(branch)

  parents = [p for p in repo.changelog.parentrevs(revision) if p >= 0]

  if len(parents)==0 and revision != 0:
    wr('reset refs/heads/%s' % branch)

  wr('commit refs/heads/%s' % branch)
  wr('mark :%d' % (revision+1))
  if sob:
    wr('author %s %d %s' % (get_author(desc,user,authors),time,timezone))
  wr('committer %s %d %s' % (user,time,timezone))
  wr('data %d' % (len(desc)+1)) # wtf?
  wr(desc)
  wr()

  ctx=repo.changectx(str(revision))
  man=ctx.manifest()
  added,changed,removed,type=[],[],[],''

  if len(parents) == 0:
    # first revision: feed in full manifest
    added=man.keys()
    added.sort()
    type='full'
  else:
    wr('from %s' % revnum_to_revref(parents[0], old_marks))
    if len(parents) == 1:
      # later non-merge revision: feed in changed manifest
      # if we have exactly one parent, just take the changes from the
      # manifest without expensively comparing checksums
      f=repo.status(repo.lookup(parents[0]),revnode)[:3]
      added,changed,removed=f[1],f[0],f[2]
      type='simple delta'
    else: # a merge with two parents
      wr('merge %s' % revnum_to_revref(parents[1], old_marks))
      # later merge revision: feed in changed manifest
      # for many files comparing checksums is expensive so only do it for
      # merges where we really need it due to hg's revlog logic
      added,changed,removed=get_filechanges(repo,revision,parents,man)
      type='thorough delta'

  sys.stderr.write('%s: Exporting %s revision %d/%d with %d/%d/%d added/changed/removed files\n' %
      (branch,type,revision+1,max,len(added),len(changed),len(removed)))

  if fn_encoding:
    removed=[r.decode(fn_encoding).encode('utf8') for r in removed]

  removed=[strip_leading_slash(x) for x in removed]

  map(lambda r: wr('D %s' % r),removed)
  export_file_contents(ctx,man,added,hgtags,fn_encoding)
  export_file_contents(ctx,man,changed,hgtags,fn_encoding)
  wr()

  return checkpoint(count)

def export_note(ui,repo,revision,count,authors,encoding,is_first):
  (revnode,_,user,(time,timezone),_,_,_,_)=get_changeset(ui,repo,revision,authors,encoding)

  parents = [p for p in repo.changelog.parentrevs(revision) if p >= 0]

  wr('commit refs/notes/hg')
  wr('committer %s %d %s' % (user,time,timezone))
  wr('data 0')
  if is_first:
    wr('from refs/notes/hg^0')
  wr('N inline :%d' % (revision+1))
  hg_hash=repo.changectx(str(revision)).hex()
  wr('data %d' % (len(hg_hash)))
  wr_no_nl(hg_hash)
  wr()
  return checkpoint(count)

  wr('data %d' % (len(desc)+1)) # wtf?
  wr(desc)
  wr()

def export_tags(ui,repo,old_marks,mapping_cache,count,authors,tagsmap):
  l=repo.tagslist()
  for tag,node in l:
    # Remap the branch name
    tag=sanitize_name(tag,"tag",tagsmap)
    # ignore latest revision
    if tag=='tip': continue
    # ignore tags to nodes that are missing (ie, 'in the future')
    if node.encode('hex_codec') not in mapping_cache:
      sys.stderr.write('Tag %s refers to unseen node %s\n' % (tag, node.encode('hex_codec')))
      continue

    rev=int(mapping_cache[node.encode('hex_codec')])

    ref=revnum_to_revref(rev, old_marks)
    if ref==None:
      sys.stderr.write('Failed to find reference for creating tag'
          ' %s at r%d\n' % (tag,rev))
      continue
    sys.stderr.write('Exporting tag [%s] at [hg r%d] [git %s]\n' % (tag,rev,ref))
    wr('reset refs/tags/%s' % tag)
    wr('from %s' % ref)
    wr()
    count=checkpoint(count)
  return count

def load_mapping(name, filename):
  cache={}
  if not os.path.exists(filename):
    sys.stderr.write('Could not open mapping file [%s]\n' % (filename))
    return cache
  f=open(filename,'r')
  l=0
  a=0
  lre=re.compile('^([^=]+)[ ]*=[ ]*(.+)$')
  for line in f.readlines():
    l+=1
    line=line.strip()
    if line=='' or line[0]=='#':
      continue
    m=lre.match(line)
    if m==None:
      sys.stderr.write('Invalid file format in [%s], line %d\n' % (filename,l))
      continue
    # put key:value in cache, key without ^:
    cache[m.group(1).strip()]=m.group(2).strip()
    a+=1
  f.close()
  sys.stderr.write('Loaded %d %s\n' % (a, name))
  return cache

def branchtip(repo, heads):
  '''return the tipmost branch head in heads'''
  tip = heads[-1]
  for h in reversed(heads):
    if 'close' not in repo.changelog.read(h)[5]:
      tip = h
      break
  return tip

def verify_heads(ui,repo,cache,force,branchesmap):
  branches={}
  for bn, heads in repo.branchmap().iteritems():
    branches[bn] = branchtip(repo, heads)
  l=[(-repo.changelog.rev(n), n, t) for t, n in branches.items()]
  l.sort()

  # get list of hg's branches to verify, don't take all git has
  for _,_,b in l:
    b=get_branch(b)
    sanitized_name=sanitize_name(b,"branch",branchesmap)
    sha1=get_git_sha1(sanitized_name)
    c=cache.get(sanitized_name)
    if sha1!=c:
      sys.stderr.write('Error: Branch [%s] modified outside hg-fast-export:'
        '\n%s (repo) != %s (cache)\n' % (b,sha1,c))
      if not force: return False

  # verify that branch has exactly one head
  t={}
  for h in repo.heads():
    (_,_,_,_,_,_,branch,_)=get_changeset(ui,repo,h)
    if t.get(branch,False):
      sys.stderr.write('Error: repository has at least one unnamed head: hg r%s\n' %
          repo.changelog.rev(h))
      if not force: return False
    t[branch]=True

  return True

def hg2git(repourl,m,marksfile,mappingfile,headsfile,tipfile,
           authors={},branchesmap={},tagsmap={},
           sob=False,force=False,hgtags=False,notes=False,encoding='',fn_encoding=''):
  def check_cache(filename, contents):
    if len(contents) == 0:
      sys.stderr.write('Warning: %s does not contain any data, this will probably make an incremental import fail\n' % filename)

  # _max=int(m)

  old_marks=load_cache(marksfile,lambda s: int(s)-1)
  mapping_cache=load_cache(mappingfile)
  heads_cache=load_cache(headsfile)
  state_cache=load_cache(tipfile)

  # old_marks = CacheFile(marksfile, lambda s: int(s) - 1)
  # mapping_cache = CacheFile(mappingfile)
  # heads_cache = CacheFile(headsfile)
  # state_cache = CacheFile(tipfile)

  if len(state_cache) != 0:
    for (name, data) in [(marksfile, old_marks),
                         (mappingfile, mapping_cache),
                         (headsfile, state_cache)]:
      check_cache(name, data)

  # if state_cache.empty():
  #     for cache in [old_marks, mapping_cache, heads_cache]:
  #         cache.check()

  ui, repo = setup_repo(repourl)

  if not verify_heads(ui,repo,heads_cache,force,branchesmap):
    return 1

  try:
    tip = repo.changelog.count()
  except AttributeError:
    tip = len(repo)

  #_max=int(m)

  min_ = int(state_cache.get('tip', 0))
  max_ = int(m)
  if max_ < 0 or max_ > tip:
    max_ = tip

  for rev in range(0, max_):
  	(revnode,_,_,_,_,_,_,_)=get_changeset(ui,repo,rev,authors)
  	mapping_cache[revnode.encode('hex_codec')] = str(rev)

  c = 0
  brmap = {}
  for rev in range(min_, max_):
    c = export_commit(ui,repo,rev,old_marks,max_,c,authors,branchesmap,
                    sob,brmap,hgtags,encoding,fn_encoding)
  if notes:
    for rev in range(min_, max_):
      c = export_note(ui, repo, rev, c, authors, encoding, rev == min_ and min_ != 0)

  state_cache['tip'] = max_
  state_cache['repo'] = repourl
  # state_cache.save()
  # mapping_cache.save()
  save_cache(tipfile, state_cache)
  save_cache(mappingfile, mapping_cache)

  c = export_tags(ui,repo,old_marks,mapping_cache,c,authors,tagsmap)

  print('Issued {} commands'.format(c), file=sys.stderr)

  return 0

def sh_main(): # pragma: no cover
    """Ported code from hg-fast-export.sh that uses this modules main func"""
    # ROOT="$(dirname "$(which "$0")")"
    # REPO=""
    GIT_DIR = subprocess.check_output('git rev-parse --git-dir'.split())
    GIT_DIR = os.path.abspath(GIT_DIR.rstrip())

    PFX = "hg2git"
    SFX_MAPPING = "mapping"
    SFX_MARKS = "marks"
    SFX_HEADS = "heads"
    SFX_STATE = "state"
    metadata_files = {
        'mapping': '{}-{}'.format(PFX, SFX_MAPPING),
        'marks': '{}-{}'.format(PFX, SFX_MARKS),
        'heads': '{}-{}'.format(PFX, SFX_HEADS),
        'state': '{}-{}'.format(PFX, SFX_STATE),
    }
    # GFI_OPTS=""
    # PYTHON=${PYTHON:-python}
    #
    # USAGE="[--quiet] [-r <repo>] [--force] [-m <max>] [-s] [--hgtags] [-A <file>] [-B <file>] [-T <file>] [-M <name>] [-o <name>] [--hg-hash] [-e <encoding>]"
    # LONG_USAGE="Import hg repository <repo> up to either tip or <max>
    # If <repo> is omitted, use last hg repository as obtained from state file,
    # GIT_DIR/$PFX-$SFX_STATE by default.
    parser = argparse.ArgumentParser(description='Import Hg repo up to tip')
    # Note: The argument order matters.
    #
    # Options:
    # 	--quiet   Passed to git-fast-import(1)
    # 	-r <repo> Mercurial repository to import
    # 	--force   Ignore validation errors when converting, and pass --force
    # 	          to git-fast-import(1)
    # 	-m <max>  Maximum revision to import
    # 	-s        Enable parsing Signed-off-by lines
    # 	--hgtags  Enable exporting .hgtags files
    # 	-A <file> Read author map from file
    # 	          (Same as in git-svnimport(1) and git-cvsimport(1))
    # 	-B <file> Read branch map from file
    # 	-T <file> Read tags map from file
    # 	-M <name> Set the default branch name (defaults to 'master')
    # 	-o <name> Use <name> as branch namespace to track upstream (eg 'origin')
    # 	--hg-hash Annotate commits with the hg hash as git notes in the
    #                   hg namespace.
    # 	-e <encoding> Assume commit and author strings retrieved from
    # 	              Mercurial are encoded in <encoding>
    # 	--fe <filename_encoding> Assume filenames from Mercurial are encoded
    # 	                         in <filename_encoding>
    # "
    # case "$1" in
    #     -h|--help)
    #       echo "usage: $(basename "$0") $USAGE"
    #       echo ""
    #       echo "$LONG_USAGE"
    #       exit 0
    # esac
    # . "$(git --exec-path)/git-sh-setup"
    # cd_to_toplevel
    'go to top-level of the git repo'

    # while case "$#" in 0) break ;; esac
    # do
    #   case "$1" in
    parser.add_argument('-r', '-repo', help="Mercurial repository to convert", type=str)
    #     -r|--r|--re|--rep|--repo)
    #       shift
    #       REPO="$1"
    #       ;;
    parser.add_argument('-q', '--quiet', help="Quiet git-fast-import", action='store_true')
    #     --q|--qu|--qui|--quie|--quiet)
    #       GFI_OPTS="$GFI_OPTS --quiet"
    #       ;;
    parser.add_argument('-f', '--force', help="Ignore validation errors when converting", action='store_true')
    #     --force)
    #       # pass --force to git-fast-import and hg-fast-export.py
    #       GFI_OPTS="$GFI_OPTS --force"
    #       break
    #       ;;
    #     -*)
    #       # pass any other options down to hg2git.py
    #       break
    #       ;;
    #     *)
    #       break
    #       ;;
    #   esac
    #   shift
    # done

    def parse_metadata_file(fn):
        data = {}
        with open(fn, 'r') as f:
            for line in f:
                key, value = line.split(' ', 1)
                assert key[0] == ':'
                data[key[1:]] = value.rstrip()
        return data

    state = parse_metadata_file(os.path.join(GIT_DIR, metadata_files['state']))
    try:
        hg_repo = state['repo']
    except KeyError:
        raise Exception('Hg repo unknown. You must specify it with -r')
    # # for convenience: get default repo from state file
    # if [ x"$REPO" = x -a -f "$GIT_DIR/$PFX-$SFX_STATE" ] ; then
    #   REPO="`grep '^:repo ' "$GIT_DIR/$PFX-$SFX_STATE" | cut -d ' ' -f 2`"
    #   echo "Using last hg repository \"$REPO\""
    # fi
    #
    # if [  -z "$REPO" ]; then
    #     echo "no repo given, use -r flag"
    #     exit 1
    # fi
    #
    # # make sure we have a marks cache
    # if [ ! -f "$GIT_DIR/$PFX-$SFX_MARKS" ] ; then
    #   touch "$GIT_DIR/$PFX-$SFX_MARKS"
    # fi
    #
    # # cleanup on exit
    # trap 'rm -f "$GIT_DIR/$PFX-$SFX_MARKS.old" "$GIT_DIR/$PFX-$SFX_MARKS.tmp"' 0
    #
    # _err1=
    # _err2=
    # exec 3>&1
    # { read -r _err1 || :; read -r _err2 || :; } <<-EOT
    # $(
    #   exec 4>&3 3>&1 1>&4 4>&-
    #   {
    #     _e1=0
    #     GIT_DIR="$GIT_DIR" $PYTHON "$ROOT/hg-fast-export.py" \
    #       --repo "$REPO" \
    #       --marks "$GIT_DIR/$PFX-$SFX_MARKS" \
    #       --mapping "$GIT_DIR/$PFX-$SFX_MAPPING" \
    #       --heads "$GIT_DIR/$PFX-$SFX_HEADS" \
    #       --status "$GIT_DIR/$PFX-$SFX_STATE" \
    #       "$@" 3>&- || _e1=$?
    #     echo $_e1 >&3
    #   } | \
    #   {
    #     _e2=0
    #     git fast-import $GFI_OPTS --export-marks="$GIT_DIR/$PFX-$SFX_MARKS.tmp" 3>&- || _e2=$?
    #     echo $_e2 >&3
    #   }
    # )
    # EOT
    # exec 3>&-
    # [ "$_err1" = 0 -a "$_err2" = 0 ] || exit 1
    #
    # # move recent marks cache out of the way...
    # if [ -f "$GIT_DIR/$PFX-$SFX_MARKS" ] ; then
    #   mv "$GIT_DIR/$PFX-$SFX_MARKS" "$GIT_DIR/$PFX-$SFX_MARKS.old"
    # else
    #   touch "$GIT_DIR/$PFX-$SFX_MARKS.old"
    # fi
    #
    # # ...to create a new merged one
    # cat "$GIT_DIR/$PFX-$SFX_MARKS.old" "$GIT_DIR/$PFX-$SFX_MARKS.tmp" \
    # | uniq > "$GIT_DIR/$PFX-$SFX_MARKS"
    #
    # # save SHA1s of current heads for incremental imports
    # # and connectivity (plus sanity checking)
    # for head in `git branch | sed 's#^..##'` ; do
    #   id="`git rev-parse refs/heads/$head`"
    #   echo ":$head $id"
    # done > "$GIT_DIR/$PFX-$SFX_HEADS"
    #
    # # check diff with color:
    # # ( for i in `find . -type f | grep -v '\.git'` ; do diff -u $i $REPO/$i ; done | cdiff ) | less -r

def main(argv):
  def bail(parser,opt):
    sys.stderr.write('Error: No %s option given\n' % opt)
    parser.print_help()
    sys.exit(2)

  parser=OptionParser()

  parser.add_option("-m","--max",type="int",dest="max",
      help="Maximum hg revision to import")
  parser.add_option("--mapping",dest="mappingfile",
      help="File to read last run's hg-to-git SHA1 mapping")
  parser.add_option("--marks",dest="marksfile",
      help="File to read git-fast-import's marks from")
  parser.add_option("--heads",dest="headsfile",
      help="File to read last run's git heads from")
  parser.add_option("--status",dest="statusfile",
      help="File to read status from")
  parser.add_option("-r","--repo",dest="repourl",
      help="URL of repo to import")
  parser.add_option("-s",action="store_true",dest="sob",
      default=False,help="Enable parsing Signed-off-by lines")
  parser.add_option("--hgtags",action="store_true",dest="hgtags",
      default=False,help="Enable exporting .hgtags files")
  parser.add_option("-A","--authors",dest="authorfile",
      help="Read authormap from AUTHORFILE")
  parser.add_option("-B","--branches",dest="branchesfile",
      help="Read branch map from BRANCHESFILE")
  parser.add_option("-T","--tags",dest="tagsfile",
      help="Read tags map from TAGSFILE")
  parser.add_option("-f","--force",action="store_true",dest="force",
      default=False,help="Ignore validation errors by force")
  parser.add_option("-M","--default-branch",dest="default_branch",
      help="Set the default branch")
  parser.add_option("-o","--origin",dest="origin_name",
      help="use <name> as namespace to track upstream")
  parser.add_option("--hg-hash",action="store_true",dest="notes",
      default=False,help="Annotate commits with the hg hash as git notes in the hg namespace")
  parser.add_option("-e",dest="encoding",
      help="Assume commit and author strings retrieved from Mercurial are encoded in <encoding>")
  parser.add_option("--fe",dest="fn_encoding",
      help="Assume file names from Mercurial are encoded in <filename_encoding>")

  (options,args)=parser.parse_args(argv)

  m=-1
  if options.max!=None: m=options.max

  if options.marksfile==None: bail(parser,'--marks')
  if options.mappingfile==None: bail(parser,'--mapping')
  if options.headsfile==None: bail(parser,'--heads')
  if options.statusfile==None: bail(parser,'--status')
  if options.repourl==None: bail(parser,'--repo')

  a={}
  if options.authorfile!=None:
    a=load_mapping('authors', options.authorfile)

  b={}
  if options.branchesfile!=None:
    b=load_mapping('branches', options.branchesfile)

  t={}
  if options.tagsfile!=None:
    t=load_mapping('tags', options.tagsfile)

  if options.default_branch!=None:
    set_default_branch(options.default_branch)

  if options.origin_name!=None:
    set_origin_name(options.origin_name)

  encoding=''
  if options.encoding!=None:
    encoding=options.encoding

  fn_encoding=encoding
  if options.fn_encoding!=None:
    fn_encoding=options.fn_encoding

  return hg2git(options.repourl,m,options.marksfile,options.mappingfile,
                  options.headsfile, options.statusfile,
                  authors=a,branchesmap=b,tagsmap=t,
                  sob=options.sob,force=options.force,hgtags=options.hgtags,
                  notes=options.notes,encoding=encoding,fn_encoding=fn_encoding)

if __name__=='__main__':
  sys.exit(main(sys.argv[1:]))
