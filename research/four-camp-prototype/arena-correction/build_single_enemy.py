"""Private owner-requested one-enemy diagnostic, retaining original asset size.

Reduce only five camp05 frozen-array Num fields to1, retaining their existing
capacity2 and backing data. No allocation, layout or original-store metadata
changes. DataBuilder independently re-exports every logical field afterwards.
"""
from pathlib import Path
import argparse, json, shutil, struct, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from randomize import load_export, sha256
from rebirth_container import write_override
from oodle_codec import OodleCodec

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config',type=Path,required=True)
parser.add_argument('--source-asset',type=Path,required=True)
parser.add_argument('--template-build',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
config=json.loads(args.config.read_text(encoding='utf-8-sig'))
source=args.template_build.resolve()
output=args.output.resolve()
original=args.source_asset.resolve()
vanilla=Path(config['vanilla_root']).resolve()
if output.is_relative_to(vanilla) or original.is_relative_to(output):
    raise ValueError('Output must not overlap original inputs')
output.mkdir(parents=True,exist_ok=False)
relative=Path('DataObject/Field/1200-GRASA/EnemyTerritory.uasset')
if sha256(original)!='1083d96d580c587a92db70d2ae9c24d71ce9a9720d9caab848117577276a43e3':
    raise ValueError('Unreviewed three-enemy source asset')
data=bytearray(original.read_bytes())
u32=lambda p:struct.unpack_from('<I',data,p)[0]
i64=lambda p:struct.unpack_from('<q',data,p)[0]
def pointer(p):
    value=i64(p)
    if value&1!=1:raise ValueError('Expected frozen relative pointer')
    return p+(value>>1)
def align(p,a):return (p+a-1)//a*a
names=[];p=u32(0x18);names_end=p+u32(0x1c)
while p<names_end:
    wide=data[p]&0x80;length=((data[p]&0x7f)<<8)|data[p+1];p+=2
    size=length*(2 if wide else 1)
    names.append(bytes(data[p:p+size]).decode('utf-16-le' if wide else 'latin-1'));p+=size
export=u32(0x34)+u32(0x38)
export_size=struct.unpack_from('<Q',data,u32(0x2c)+8)[0]
if export+export_size!=len(data):raise ValueError('Not a single-export package')
base=export+0x20;frozen_end=base+u32(export+0xc)
patches={};p=frozen_end+8;patch_count=u32(p);p+=4
for _ in range(patch_count):
    name,number,count=struct.unpack_from('<iii',data,p);p+=12
    if not 0<=name<len(names):raise ValueError('Invalid patched name')
    for _ in range(count):patches[base+u32(p)]=(names[name],number);p+=4
keys=pointer(base);row_count=u32(base+8)
props=pointer(base+0x38);prop_count=u32(base+0x40)
entries=pointer(base+0x48)
if row_count!=44 or u32(base+0x50)!=44:raise ValueError('Unexpected row population')
def name_at(position):
    name,number=patches[position]
    return name if number==0 else f'{name}_{number-1}'
indices={name_at(keys+20*i):u32(keys+20*i+8) for i in range(row_count)}
if len(indices)!=44:raise ValueError('Duplicate row keys')
sizes={1:1,2:1,3:1,4:2,6:4,7:4,8:8,9:4,10:16,11:8}
fields={};offset=0;row_align=1
for i in range(prop_count):
    record=props+12*i;name=name_at(record);kind=u32(record+8)
    is_array=name.endswith('_Array')
    alignment=8 if is_array or kind==10 else 4 if kind==11 else sizes[kind]
    offset=align(offset,alignment);fields[name]=(offset,is_array)
    offset+=16 if is_array else sizes[kind];row_align=max(row_align,alignment)
stride=align(offset,row_align)
changes={
    'MobTemplateList_Array':'mobgrasa_Mandragora_00',
    'MobLevelList_Array':'15',
    'MinPopList_Array':'1',
    'MaxPopList_Array':'1',
    'FieldAINameList_Array':'1',
}
offsets=[]
for name in changes:
    offset,is_array=fields[name]
    if not is_array:raise ValueError('Expected array property')
    descriptor=entries+stride*indices['Grassland_mob_05']+offset
    if not base<=descriptor<frozen_end-16:raise ValueError('Descriptor outside image')
    if (u32(descriptor+8),u32(descriptor+12))!=(2,2):raise ValueError('Expected Num2/Max2')
    backing=pointer(descriptor)
    if not base<=backing<frozen_end:raise ValueError('Backing outside image')
    struct.pack_into('<I',data,descriptor+8,1)
    offsets.append({'property':name,'num_offset':descriptor+8,'before_num':2,'after_num':1,'capacity':2})
changed=[i for i,(a,b) in enumerate(zip(original.read_bytes(),data,strict=True)) if a!=b]
if changed!=sorted(v['num_offset'] for v in offsets):raise ValueError('Unexpected binary changes')
stage=output/'staging/End/Content'/relative;stage.parent.mkdir(parents=True)
stage.write_bytes(data)
builder=ROOT/'tools/DataBuilder/bin/Release/net8.0/TrainingDummy.DataBuilder.dll'
def run(args):subprocess.run([str(x) for x in args],check=True)
run(['dotnet',builder,'export',original,output/'before.csv'])
run(['dotnet',builder,'export',stage,output/'after.csv'])
before=load_export(output/'before.csv');after=load_export(output/'after.csv')
wanted={name:dict(row) for name,row in before.items()}
wanted['Grassland_mob_05'].update(changes)
if after!=wanted:raise ValueError('Independent complete table comparison differs')
package=output/'package-corrected';package.mkdir()
toc=(source/'package-corrected/BiomeRandomizer_P.utoc').read_bytes()
codec=OodleCodec(Path(config['packager']).parent/'oo2core_9_win64.dll')
verification=write_override(package/'BiomeRandomizer_P',toc,stage,codec)
shutil.copyfile(source/'package-corrected/BiomeRandomizer_P.pak',package/'BiomeRandomizer_P.pak')
# Use the independently known original territory chunk ID for cross-tool decode.
decoded=output/'independent-decoded.bin'
run([config['retoc'],'get',package/'BiomeRandomizer_P.utoc','c106a8be413015ad00000002',decoded])
if decoded.read_bytes()!=bytes(data):raise ValueError('Independent retoc decode differs')
audit={'diagnostic':'single-mandragora-only05','release_eligible':False,'native_validation':'pending',
       'target':'Grassland_mob_05','templates':['mobgrasa_Mandragora_00'],'levels':[15],'counts':[1],
       'difficulty':'unchanged Hard','requires_arena_correction':'camp05 S12 from existing M12',
       'source_asset_sha256':sha256(original),'modified_asset_sha256':sha256(stage),
       'asset_bytes':len(data),'binary_num_field_edits':offsets,
       'all_other_rows_and_properties_independently_unchanged':True,
       'package_directory':'package-corrected','container_verification':verification,
       'package':[{'name':f'BiomeRandomizer_P{ext}','sha256':sha256(package/f'BiomeRandomizer_P{ext}'),
                   'bytes':(package/f'BiomeRandomizer_P{ext}').stat().st_size} for ext in ('.pak','.ucas','.utoc')]}
(output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(output),'target':'Grassland_mob_05','enemies':1,'asset_bytes':len(data),'changed_bytes':len(changed),'native_validation':'pending'}))
