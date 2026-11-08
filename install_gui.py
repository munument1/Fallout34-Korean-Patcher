"""User-facing file-picker for the terrain-preserving Fallout 34 Korean patcher."""
from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from pathlib import Path
import os
import sys

ROOT=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)
      else Path(__file__).resolve().parent)
sys.path.insert(0,str(ROOT/'tools'))
from build_mo2_korean_mod import build


def choose_output_root(selected:Path)->Path:
    """Treat an existing user-selected folder as a parent, never overwrite it.

    A manually entered non-existing path is used as-is. If the folder exists,
    create a uniquely named child for the build, keeping any earlier results.
    """
    selected=selected.expanduser()
    if selected.is_symlink():
        raise ValueError('출력 위치에 바로가기/심볼릭 링크를 지정할 수 없습니다.')
    if not selected.exists():
        return selected
    if not selected.is_dir():
        raise ValueError('출력 위치가 폴더가 아닙니다. 폴더를 선택해 주세요.')
    base=selected/'Fallout34-Korean-Output'
    if not base.exists() and not base.is_symlink():
        return base
    for n in range(2,1001):
        candidate=selected/f'Fallout34-Korean-Output ({n})'
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise ValueError('출력 폴더 이름이 이미 너무 많이 사용되었습니다. 다른 폴더를 지정하세요.')


class UI:
    def __init__(self):
        self.app=tk.Tk()
        self.app.title('Fallout 34 한국어 패처 — MO2용 복사본 생성')
        self.app.geometry('760x355')
        self.app.minsize(690,320)
        self.fo3=tk.StringVar(value='')
        self.dest=tk.StringVar(value='')
        self.allow_updated=tk.BooleanVar(value=False)
        self.info=tk.StringVar(value='Fallout34.esm만 선택하면 같은 폴더의 FalloutNV34.esm도 자동으로 불러옵니다.')
        self.events=queue.Queue()
        self.building=False

        frame=ttk.Frame(self.app,padding=18);frame.pack(fill=tk.BOTH,expand=True)
        ttk.Label(frame,text='Fallout34 / FalloutNV34 / Fallout4 통합 한국어 패치',font=('맑은 고딕',14,'bold')).pack(anchor='w')
        ttk.Label(frame,text='원본 ESM을 변경하지 않고 복사본만 생성합니다. 게임 Data의 지형·메쉬·텍스처·BA2는 그대로 유지합니다.',wraplength=710).pack(anchor='w',pady=(5,15))

        def row(label,var,mode):
            ttk.Label(frame,text=label).pack(anchor='w')
            line=ttk.Frame(frame);line.pack(fill=tk.X,pady=(3,10))
            ttk.Entry(line,textvariable=var).pack(side=tk.LEFT,fill=tk.X,expand=True)
            ttk.Button(line,text='찾기',command=lambda:self.pick(var,mode),width=8).pack(side=tk.LEFT,padx=(8,0))

        row('① Fallout34.esm 위치 (같은 폴더의 FalloutNV34.esm 자동 선택)',self.fo3,'fo3')
        row('② 결과물을 저장할 폴더 (기존 폴더 선택 가능)',self.dest,'output')
        ttk.Checkbutton(frame,variable=self.allow_updated,
                        text='업데이트된 Fallout34 ESM 호환 시도 (기존 번역만 안전하게 재적용)').pack(anchor='w',pady=(0,5))
        self.button=ttk.Button(frame,text='한국어 MO2 모드 생성',command=self.start)
        self.button.pack(anchor='w',pady=4)
        ttk.Label(frame,textvariable=self.info,wraplength=700,foreground='#1f5668').pack(anchor='w',pady=(10,0))
        ttk.Label(frame,text='새 포팅 빌드는 원문 해시와 지형 레코드를 검사합니다. 신규/수정 문구는 미번역일 수 있으며 검토 보고서를 생성합니다.',wraplength=700).pack(anchor='w',pady=(8,0))
        self.app.after(150,self.poll)

    def pick(self,var,mode):
        if mode=='output':
            folder=filedialog.askdirectory(title='결과물을 저장할 폴더 선택')
            if folder:var.set(folder)
            return
        name='Fallout34.esm'
        chosen=filedialog.askopenfilename(title=f'{name} 선택',filetypes=[('ESM 플러그인','*.esm'),('모든 파일','*.*')])
        if chosen:
            var.set(chosen)
            candidate=Path(chosen).with_name('FalloutNV34.esm')
            if candidate.is_file():
                self.info.set('두 ESM 확인: Fallout34.esm + FalloutNV34.esm')
            else:
                self.info.set('FalloutNV34.esm이 같은 폴더에 없습니다. 변환기 출력을 확인하세요.')

    def start(self):
        if self.building:return
        file=Path(self.fo3.get().strip())
        if not file.is_file() or file.name.casefold()!='fallout34.esm':
            messagebox.showerror('원본 ESM 선택 오류','올바른 Fallout34.esm 파일을 선택해 주세요.')
            return
        nv=file.with_name('FalloutNV34.esm')
        if not nv.is_file():
            messagebox.showerror('뉴베가스 ESM 누락','선택한 Fallout34.esm과 같은 폴더에서 FalloutNV34.esm을 찾지 못했습니다.')
            return
        if not self.dest.get().strip():
            messagebox.showerror('출력 경로 누락','결과물을 저장할 폴더를 선택해 주세요.')
            return
        selected_output=Path(self.dest.get().strip())
        allow_updated=self.allow_updated.get()
        self.building=True;self.button.configure(state=tk.DISABLED)
        self.info.set('원본 ESM의 지형·번역 데이터 호환성을 확인하고 있습니다.')
        def job():
            try:
                output=choose_output_root(selected_output)
                result=build(fo3_path=file,fnv_path=nv,output_root=output,
                    allow_updated_esms=allow_updated,
                    progress=lambda msg:self.events.put(('progress',msg)))
                self.events.put(('done',(str(output/'Fallout34 Unified Korean'),result)))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=job,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='progress':self.info.set(data)
                elif kind=='done':
                    self.building=False;self.button.configure(state=tk.NORMAL)
                    self.info.set('성공: '+data[0])
                    updated=any(x['updated_converter_input'] for x in data[1]['translations'].values())
                    text='MO2에서 새 모드로 등록할 폴더를 만들었습니다.\n\n'+data[0]+(
                      '\n\n업데이트된 ESM은 새로운 문구의 번역과 인게임 검증이 별도로 필요합니다.'
                      if updated else '')+'\n\n원본 게임 및 Data 파일은 변경되지 않았습니다.'
                    if data[1]['status']=='REVIEW_REQUIRED':
                        messagebox.showwarning('한국어 패치 생성: 검토 필요',
                            text+'\n\nbuild-report.json의 unmatched_fields를 확인하세요.')
                    else:messagebox.showinfo('한국어 패치 생성 완료',text)
                elif kind=='error':
                    self.building=False;self.button.configure(state=tk.NORMAL)
                    self.info.set('안전 검증 실패 — 결과물을 설치하지 않았습니다.')
                    messagebox.showerror('패치 중단',data)
        except queue.Empty:pass
        self.app.after(150,self.poll)

    def run(self):self.app.mainloop()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--cli':
        # Also allows a headless end-to-end test of the *frozen* EXE using a
        # real user-owned converter ESM, without opening any game UI.
        if sys.stdout is None:sys.stdout=open(os.devnull,'w',encoding='utf-8')
        if sys.stderr is None:sys.stderr=open(os.devnull,'w',encoding='utf-8')
        sys.argv.pop(1)
        from build_mo2_korean_mod import main
        main()
    elif len(sys.argv)>1 and sys.argv[1]=='--verify-bundle':
        if sys.stdout is None:sys.stdout=open(os.devnull,'w',encoding='utf-8')
        if sys.stderr is None:sys.stderr=open(os.devnull,'w',encoding='utf-8')
        from build_mo2_korean_mod import load_canonical,source_preflight,MANIFEST
        from fo4_korean_assets import select_assets
        import json
        manifest=json.loads(MANIFEST.read_text('utf-8'))
        if manifest['schema']!=2:raise ValueError('Unsupported manifest')
        for game,meta in manifest['games'].items():
            plan,_=load_canonical(game,meta)
            print(game, 'translations',len(plan),flush=True)
        assets=select_assets()
        print('bundle PASS',assets['asset_count'],flush=True)
    elif len(sys.argv)>1:
        raise SystemExit('Unknown argument; run without arguments for GUI, or use --verify-bundle / --cli')
    else:
        UI().run()
