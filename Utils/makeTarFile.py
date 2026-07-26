import fnmatch
import tarfile
import os

EXCLUDE_FILES = [".tmp", ".log", ".stdout", ".stderr"]
EXCLUDE_PATTERNS = [
    "*_cc.d",
]

def filter_function(tarinfo):
    """
    Helper function for creating the tarball.

    This function filters out unwanted files to be added to the tarball.

    Arguments:
        tarinfo {TarInfo} -- TarInfo object

    Returns:
        bool -- True if the file should be included, False otherwise.
    """
    basename = os.path.basename(tarinfo.name)
    if os.path.splitext(tarinfo.name)[1] in EXCLUDE_FILES:
        return None
    if any(fnmatch.fnmatch(basename, pattern) for pattern in EXCLUDE_PATTERNS):
        return None
    else:
        return tarinfo

def make_tarfile(source_dir, output_filename):
    """
    Create a tarball from a given directory.

    Arguments:
        source_dir {string} -- Name of the directory to be tarballed.
        output_filename {string} -- Output file name for the tarball.
    """
    with tarfile.open(output_filename, "w:gz") as tar:
        print("make_tarfile:: Started creating tar file...")
        tar.add(source_dir, arcname=os.path.basename(source_dir), filter=filter_function)
        print("make_tarfile:: Done...")
