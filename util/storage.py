from server import supabase
import os, uuid

def validate_file(file_data,toggle):
    file_header = file_data.read(12)
    file_data.seek(0)
    if file_header.startswith(b'\xff\xd8\xff'):
        return '.jpg','image/jpeg'
    elif file_header.startswith(b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'):
        return '.png','image/png'
    elif (file_header[0:4]==(b'\x52\x49\x46\x46') and file_header[8:12] == (b'\x57\x45\x42\x50')):
        return '.webp','image/webp'
    elif toggle and (file_header.startswith(b'\x47\x49\x46\x38\x37\x61') or file_header.startswith(b'\x47\x49\x46\x38\x39\x61')):
        return '.gif','image/gif'
    else:
        return None, None

def bucket_upload(file,bucket,dest,user):
    if not file:
        raise ValueError('no file sent or illegal actions')

    allow_ImgFormat = [['image/jpg','image/jpeg','image/png','image/webp','image/gif'],['jpg','jpeg','png','webp','gif']]
    if not (file.content_type in allow_ImgFormat[0]):
        if '.' in file.filename and not (file.filename.split('.')[-1].lower() in allow_ImgFormat[1]):
            raise ValueError('file format not allowed')
    
    if dest == 'content':
        signature,content_type = validate_file(file_data=file, toggle=True)
    else:
        signature,content_type = validate_file(file_data=file, toggle=False)
    if not signature:
        raise ValueError('file format not allowed')
    
    if bucket == 'avatars':
        max_size = (2*1024*1024)
    elif signature == '.gif':
        max_size = (10*1024*1024)
    else:
        max_size = (5*1024*1024)

    file.seek(0,os.SEEK_END)
    if (file.tell() >  max_size):
        raise ValueError('file size limit exceeded')
    else:
        file.seek(0)

    file_storage_name = f'{user}/{str(uuid.uuid4())}{signature}'

    try:
        file_storage_data = file.read()
        supabase.storage.from_(bucket).upload(
            file_storage_name,
            file_storage_data,
            {'content-type':content_type}
        )
        public_url = supabase.storage.from_(bucket).get_public_url(file_storage_name)
    except Exception as e:
        raise RuntimeError(f'upload failure, {str(e)}')
    
    
    return public_url

def bucket_remove(file_path,bucket):
    file_storage_name = "/".join(file_path.split('/')[-2:])
    try:
        supabase.storage.from_(bucket).remove([file_storage_name])
    except Exception as e:
        raise RuntimeError(f'image remove failure because {e}')


    
    

    
    
    
