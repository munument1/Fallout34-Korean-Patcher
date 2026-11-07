"""User-facing file-picker for the terrain-preserving Fallout 34 Korean patcher."""
from __future__ import annotations
import queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from build_mo2_korean_mod import build


class UI:
    def __init__(self):
        self.app=tk.Tk()
        self.app.title('Fallout 34 한국어 패처 — MO2용 복사본 생성')
        self.app.geometry('760x400')
        self.app.minsize(690,340)
        self.fo3=tk.StringVar(value='')
        self.fnv=tk.StringVar(value='')
        self.dest=tk.StringVar(value=str(Path.home()/'Documents'/'Fallout34-Korean-Output'))
        self.info=tk.StringVar(value='Fallout34.esm을 선택해 주세요. FalloutNV34.esm은 같은 폴더에서 자동으로 찾습니다.')
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

        row('① Fallout34.esm 위치 (필수)',self.fo3,'fo3')
        row('② FalloutNV34.esm 위치 (같은 폴더면 비워두기)',self.fnv,'fnv')
        row('③ MO2용 결과물을 생성할 새 폴더',self.dest,'output')
        self.button=ttk.Button(frame,text='한국어 MO2 모드 생성',command=self.start)
        self.button.pack(anchor='w',pady=4)
        ttk.Label(frame,textvariable=self.info,wraplength=700,foreground='#1f5668').pack(anchor='w',pady=(10,0))
        ttk.Label(frame,text='지원하는 원본 포팅 빌드만 허용합니다. ESM 버전이 다르면 지형 보호를 위해 안전하게 중단합니다.',wraplength=700).pack(anchor='w',pady=(8,0))
        self.app.after(150,self.poll)

    def pick(self,var,mode):
        if mode=='output':
            folder=filedialog.askdirectory(title='출력 폴더를 만들 부모 경로 선택')
            if folder:var.set(str(Path(folder)/'Fallout34-Korean-Output'))
            return
        name='Fallout34.esm' if mode=='fo3' else 'FalloutNV34.esm'
        chosen=filedialog.askopenfilename(title=f'{name} 선택',filetypes=[('ESM 플러그인','*.esm'),('모든 파일','*.*')])
        if chosen:
            var.set(chosen)
            if mode=='fo3' and not self.fnv.get():
                candidate=Path(chosen).with_name('FalloutNV34.esm')
                if candidate.is_file():self.fnv.set(str(candidate))

    def start(self):
        if self.building:return
        file=Path(self.fo3.get().strip())
        if not file.is_file() or file.name.casefold()!='fallout34.esm':
            messagebox.showerror('원본 ESM 선택 오류','올바른 Fallout34.esm 파일을 선택해 주세요.')
            return
        nv=Path(self.fnv.get().strip()) if self.fnv.get().strip() else file.with_name('FalloutNV34.esm')
        output=Path(self.dest.get().strip())
        if not nv.is_file():
            messagebox.showerror('뉴베가스 ESM 누락','FalloutNV34.esm을 찾지 못했습니다. 파일을 선택해 주세요.')
            return
        if not self.dest.get().strip():
            messagebox.showerror('출력 경로 누락','새 출력 폴더 경로를 선택해 주세요.')
            return
        self.building=True;self.button.configure(state=tk.DISABLED)
        self.info.set('원본 ESM의 지형·번역 데이터 호환성을 확인하고 있습니다.')
        def job():
            try:
                result=build(fo3_path=file,fnv_path=nv,output_root=output,
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
                    messagebox.showinfo('한국어 패치 생성 완료',
                      'MO2에서 새 모드로 등록할 폴더를 만들었습니다.\n\n'+data[0]+
                      '\n\n원본 게임 및 Data 파일은 변경되지 않았습니다.')
                elif kind=='error':
                    self.building=False;self.button.configure(state=tk.NORMAL)
                    self.info.set('안전 검증 실패 — 결과물을 설치하지 않았습니다.')
                    messagebox.showerror('패치 중단',data)
        except queue.Empty:pass
        self.app.after(150,self.poll)

    def run(self):self.app.mainloop()


if __name__=='__main__':UI().run()
