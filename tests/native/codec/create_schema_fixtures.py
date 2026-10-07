#!/usr/bin/env python3
"""Create schema/asset codec fixtures in a caller-selected output directory."""
import argparse, copy, json, os, pathlib, struct, zipfile, zlib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--font', type=pathlib.Path, default=os.environ.get('THEME_CODEC_FONT'))
parser.add_argument('--font-license', default=os.environ.get('THEME_CODEC_FONT_LICENSE', 'Host test fixture'))
args = parser.parse_args()
if not args.font or not args.font.is_file():
    parser.error('--font or THEME_CODEC_FONT must select a licensed host TTF file')
if not args.font_license or len(args.font_license) > 100:
    parser.error('--font-license must contain 1..100 characters')
FONT_BYTES = args.font.read_bytes()
OUT = args.output.resolve()
REPO = pathlib.Path(__file__).resolve().parents[3]
if OUT == REPO or REPO in OUT.parents:
    parser.error('--output must be outside the repository')
OUT.mkdir(parents=True, exist_ok=True)
BASE = args.baseline
with zipfile.ZipFile(BASE) as z:
    baseline = {name: z.read(name) for name in z.namelist()}
base_manifest = json.loads(baseline['manifest.json'])
base_tokens = json.loads(baseline['tokens/dark.json'])
expect = []

def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()

def bundle(name, files, accept=False, note=''):
    with zipfile.ZipFile(OUT / (name + '.ouitheme'), 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for key, value in files.items():
            z.writestr(key, value)
    expect.append(dict(path='schema/' + name + '.ouitheme', accept=accept, note=note))

def mutation(name, transform, *, accept=False, note=''):
    m, t = copy.deepcopy(base_manifest), copy.deepcopy(base_tokens)
    f = dict(baseline)
    transform(m, t, f)
    f['manifest.json'], f['tokens/dark.json'] = encoded(m), encoded(t)
    bundle(name, f, accept, note)

def png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = (b'\x00' + b'\xff\x00\x99\xff' * width) * height
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')

def rich(m, t, f):
    m['name'] = 'Unicode fixture Ω ✨'
    m['variants']['light'] = 'tokens/light.json'
    light = copy.deepcopy(t)
    light['background']['value'] = '#FFF7F8FA'
    f['tokens/light.json'] = encoded(light)
    m['assets'] = [
        {'path':'assets/icon.png','kind':'icon','license':'fixture'},
        {'path':'assets/wallpaper.png','kind':'wallpaper','license':'fixture'},
        {'path':'assets/font.ttf','kind':'font','license':args.font_license}]
    f['assets/icon.png'] = png(2, 2)
    f['assets/wallpaper.png'] = png(3, 2)
    f['assets/font.ttf'] = FONT_BYTES
    t['bodyFont'] = {'type':'fontAsset','value':'assets/font.ttf'}
    t['headlineFont'] = {'type':'fontAsset','value':'assets/font.ttf'}
    t['cornerRadius'] = {'type':'dimension','value':16.5,'unit':'dp'}
    t['quickTileRadius'] = {'type':'dimension','value':32,'unit':'dp'}
    t['keyboardKeyRadius'] = {'type':'dimension','value':24,'unit':'dp'}
    t['navigationBarHeight'] = {'type':'dimension','value':96,'unit':'dp'}
    t['bodyTextSize'] = {'type':'dimension','value':28,'unit':'sp'}
    t['outline'] = {'type':'color','value':'#80112233'}
    m['components'].extend([{'id':'typography','required':False},{'id':'launcher.icons','required':False},{'id':'component.drawables','required':False},{'id':'extension:org.example/app.palette','required':False}])
    m['stylePack'] = {'id':'org.example.styles','version':'1.2.3'}
    m['appearance'] = {'dark':{
        'icons':{'quickPanel.wifi':'assets/icon.png'},
        'components':{
            'quickTile':{'shape':'roundedRectangle','fillRole':'quickTileInactive','radiusRole':'quickTileRadius','strokeRole':'outline','strokeWidthDp':1.5},
            'keyboardKey':{'shape':'roundedRectangle','fillRole':'surface','radiusRole':'keyboardKeyRadius'},
            'card':{'shape':'roundedRectangle','fillRole':'surface','radiusRole':'cornerRadius'},
            'dialog':{'shape':'rectangle','fillRole':'surface'},
            'button':{'shape':'circle','fillRole':'accent'}}},
        'light':{'icons':{'quickPanel.wifi':'assets/icon.png'}}}
    m['overrides'] = {'dark':'overrides/dark.json','light':'overrides/light.json'}
    f['overrides/dark.json'] = encoded({'keyboard':{'keyboardBackground':{'type':'color','value':'#FF101010'},'bodyFont':{'type':'fontAsset','value':'assets/font.ttf'}},'extension:org.example/app.palette':{'accent':{'type':'color','value':'#80ABCDEF'}}})
    f['overrides/light.json'] = encoded({'systemui':{'quickPanelBackground':{'type':'color','value':'#FFEEDDCC'}}})

mutation('valid-rich', rich, accept=True, note='Both variants, font/icon/wallpaper assets, all appearance shapes, dimensions, style-pack and extension overrides.')
with zipfile.ZipFile(OUT/'valid-rich.ouitheme') as z:
    richfiles = {n:z.read(n) for n in z.namelist()}
richmanifest = json.loads(richfiles['manifest.json'])
richtokens = json.loads(richfiles['tokens/dark.json'])

def richmut(name, transform, note=''):
    m, t, f = copy.deepcopy(richmanifest), copy.deepcopy(richtokens), dict(richfiles)
    transform(m, t, f)
    f['manifest.json'], f['tokens/dark.json'] = encoded(m), encoded(t)
    bundle(name, f, False, note)

mutation('missing-required-manifest', lambda m,t,f:m.pop('author'))
mutation('unknown-manifest-property', lambda m,t,f:m.update(shell='echo hi'))
mutation('invalid-source-api', lambda m,t,f:m.update(format='oneui-studio.source/2'))
mutation('invalid-token-api', lambda m,t,f:m.update(tokenApi='oneui-studio.tokens/2'))
mutation('invalid-id', lambda m,t,f:m.update(id='../../theme'))
mutation('invalid-version', lambda m,t,f:m.update(version='1.0'))
mutation('invalid-target-major-type', lambda m,t,f:m['targetIntent'].update(uiMajor='9'))
mutation('invalid-component-required-type', lambda m,t,f:m['components'][0].update(required='false'))
mutation('duplicate-component', lambda m,t,f:m['components'].append(copy.deepcopy(m['components'][0])))
mutation('bad-extension-component', lambda m,t,f:m['components'].append({'id':'extension:INVALID/app','required':False}))
mutation('required-extension-syntax-valid', lambda m,t,f:m['components'].append({'id':'extension:org.example/app.palette','required':True}), accept=True, note='Codec stores intention; resolution belongs to compatibility/compiler layer.')
mutation('missing-required-token', lambda m,t,f:t.pop('surface'))
mutation('unknown-token-role', lambda m,t,f:t.update(rawResource={'type':'color','value':'#FF112233'}))
mutation('color-lowercase', lambda m,t,f:t['accent'].update(value='#ffaabbcc'))
mutation('color-six-digit', lambda m,t,f:t['accent'].update(value='#AABBCC'))
mutation('wrong-token-type', lambda m,t,f:t['accent'].update(type='dimension'))
mutation('extra-token-property', lambda m,t,f:t['accent'].update(unit='dp'))
mutation('dimension-wrong-unit', lambda m,t,f:t.update(bodyTextSize={'type':'dimension','value':14,'unit':'dp'}))
mutation('dimension-out-of-range', lambda m,t,f:t.update(quickTileRadius={'type':'dimension','value':33,'unit':'dp'}))
mutation('font-reference-undeclared', lambda m,t,f:t.update(bodyFont={'type':'fontAsset','value':'assets/missing.ttf'}))
mutation('overrides-undeclared-variant', lambda m,t,f:m.update(overrides={'light':'overrides/light.json'}))
mutation('appearance-undeclared-variant', lambda m,t,f:m.update(appearance={'light':{'icons':{'quickPanel.wifi':'assets/icon.png'}}}))
mutation('missing-license', lambda m,t,f:f.pop('LICENSE.txt'))
mutation('missing-tokens', lambda m,t,f:f.pop('tokens/dark.json'), note='Token file is reset by helper; use separate missing entry below.')
expect.pop(); (OUT/'missing-tokens.ouitheme').unlink()
missing = dict(baseline); missing.pop('tokens/dark.json'); bundle('missing-tokens', missing)

richmut('font-reference-wrong-kind', lambda m,t,f:m['assets'][2].update(kind='icon'))
richmut('font-asset-invalid-magic', lambda m,t,f:f.update({'assets/font.ttf':b'not a real font'}))
richmut('missing-icon-file', lambda m,t,f:f.pop('assets/icon.png'))
richmut('duplicate-asset', lambda m,t,f:m['assets'].append(copy.deepcopy(m['assets'][0])))
richmut('appearance-icon-undeclared', lambda m,t,f:m['appearance']['dark']['icons'].update({'quickPanel.wifi':'assets/missing.png'}))
richmut('appearance-icon-wallpaper-kind', lambda m,t,f:m['appearance']['dark']['icons'].update({'quickPanel.wifi':'assets/wallpaper.png'}))
richmut('appearance-icon-invalid-slot', lambda m,t,f:m['appearance']['dark']['icons'].update({'../rawResource':'assets/icon.png'}))
richmut('appearance-extra-property', lambda m,t,f:m['appearance']['dark'].update(shell='echo hi'))
richmut('appearance-invalid-shape', lambda m,t,f:m['appearance']['dark']['components']['button'].update(shape='rawXml'))
richmut('appearance-invalid-color-role', lambda m,t,f:m['appearance']['dark']['components']['button'].update(fillRole='unknown'))
richmut('appearance-invalid-radius-role', lambda m,t,f:m['appearance']['dark']['components']['quickTile'].update(radiusRole='bodyTextSize'))
richmut('appearance-stroke-out-of-range', lambda m,t,f:m['appearance']['dark']['components']['quickTile'].update(strokeWidthDp=9))
richmut('appearance-unknown-component', lambda m,t,f:m['appearance']['dark']['components'].update(unknown={'shape':'circle','fillRole':'accent'}))
richmut('override-unknown-target', lambda m,t,f:f.update({'overrides/dark.json':encoded({'com.android.systemui':{'accent':{'type':'color','value':'#FF112233'}}})}))
richmut('override-bad-extension-target', lambda m,t,f:f.update({'overrides/dark.json':encoded({'extension:INVALID/app':{'accent':{'type':'color','value':'#FF112233'}}})}))
richmut('override-bad-font-reference', lambda m,t,f:f.update({'overrides/dark.json':encoded({'keyboard':{'bodyFont':{'type':'fontAsset','value':'assets/missing.ttf'}}})}))
richmut('image-invalid-payload', lambda m,t,f:f.update({'assets/icon.png':b'not a png'}))
richmut('image-wrong-format', lambda m,t,f:f.update({'assets/icon.png':b'\xff\xd8\xff\xe0not valid jpeg'}))
richmut('image-too-wide', lambda m,t,f:f.update({'assets/icon.png':png(8193,1)}))
richmut('image-too-high', lambda m,t,f:f.update({'assets/icon.png':png(1,8193)}))

rawcases = {
    'json-duplicate-root':baseline['manifest.json'].replace(b'"name": "AMOLED Black"', b'"name": "AMOLED Black", "name": "Other"'),
    'json-escaped-duplicate-root':baseline['manifest.json'].replace(b'"name": "AMOLED Black"', b'"name": "AMOLED Black", "na\\u006de": "Other"'),
    'json-duplicate-nested':baseline['manifest.json'].replace(b'"manufacturer": "Samsung"',b'"manufacturer": "Samsung", "manufacturer": "Samsung"'),
    'json-trailing-content':baseline['manifest.json']+b'{}',
    'json-single-quotes':baseline['manifest.json'].replace(b'"name": "AMOLED Black"', b"'name': 'AMOLED Black'"),
    'json-trailing-comma':baseline['manifest.json'].rstrip().removesuffix(b'}')+b',}',
    'json-comment':b'/*comment*/'+baseline['manifest.json'],
    'json-unquoted-key':baseline['manifest.json'].replace(b'"name":',b'name:'),
    'json-invalid-utf8':baseline['manifest.json'].replace(b'AMOLED Black',b'AMOLED\xffBlack'),
    'json-unpaired-surrogate':baseline['manifest.json'].replace(b'AMOLED Black',b'AMOLED \\ud800'),
    'json-primitive':b'false',
    'json-over-limit':baseline['manifest.json']+b' '*(1024*1024-len(baseline['manifest.json'])+1),
}
for name, value in rawcases.items():
    files=dict(baseline); files['manifest.json']=value; bundle(name,files)
files=dict(baseline)
files['tokens/dark.json']=baseline['tokens/dark.json'].replace(b'"accent": {"type": "color", "value": "#FF00E5FF"}', b'"accent": {"type": "color", "value": "#FF00E5FF"}, "accent": {"type": "color", "value": "#FF00E5FF"}')
bundle('json-duplicate-token-role', files)
files=dict(baseline)
files['tokens/dark.json']=baseline['tokens/dark.json'].replace(b'"value": "#FF00E5FF"', b'"value": "#FF00E5FF", "value": "#FF00E5FF"')
bundle('json-duplicate-token-property', files)
files=dict(richfiles)
files['overrides/dark.json']=b'{"keyboard":{"accent":{"type":"color","value":"#FF112233"}},"keyboard":{"accent":{"type":"color","value":"#FF112233"}}}'
bundle('json-duplicate-override-target', files)
files=dict(baseline)
files['tokens/dark.json']=baseline['tokens/dark.json'].rstrip().removesuffix(b'}')+b',"cornerRadius":{"type":"dimension","value":32.000000000000000001,"unit":"dp"}}'
bundle('json-dimension-over-bound-precise', files)
files=dict(baseline)
files['manifest.json']=baseline['manifest.json'].replace(b'"uiMajor": 9', b'"uiMajor": 9.000000000000000001')
bundle('json-ui-major-fraction-precise', files)
files=dict(baseline)
files['manifest.json']=baseline['manifest.json'].replace(b'AMOLED Black', 'AMOLED \\uＦＦＦＦ'.encode())
bundle('json-unicode-escape-non-ascii-hex', files)
files=dict(baseline); files['manifest.json'] += b' '*(1024*1024-len(files['manifest.json'])); bundle('valid-json-limit', files, True)
def reordered(value):
    if isinstance(value, dict):
        return {key:reordered(item) for key,item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reordered(item) for item in value]
    return value
files={n:(encoded(reordered(json.loads(v))) if n.endswith('.json') else v) for n,v in reversed(list(richfiles.items()))}
bundle('valid-rich-reordered', files, True, 'Same source with JSON and ZIP entry ordering changed.')
(OUT/'expectations.json').write_text(json.dumps(expect, indent=2)+'\n')
print(f'Created {len(expect)} schema/asset fixtures in {OUT}')
