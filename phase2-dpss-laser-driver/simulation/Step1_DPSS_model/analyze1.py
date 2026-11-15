import numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Liberation Serif','font.size':9,'axes.linewidth':0.7,'mathtext.fontset':'stix'})
dc=np.loadtxt('dc_iv.txt'); I=dc[:,0]*1e3; V=dc[:,1]; P=dc[:,3]*1e3
fig,ax=plt.subplots(figsize=(3.5,2.4)); ax.plot(I,V,'k-',lw=1,label='Voltage'); ax.set_xlabel('Pump current (mA)'); ax.set_ylabel('Forward voltage (V)'); ax.set_ylim(0,2.5); ax.set_xlim(0,460)
ax2=ax.twinx(); ax2.plot(I,P,'k--',lw=1,label='Optical power'); ax2.set_ylabel('532 nm output (mW)'); ax2.set_ylim(0,90)
Id=[200,250,300,320,350,380,400,430,450]; Pd=[1,6,20,25,37,50,60,75,83]; ax2.plot(Id,Pd,'o',color='0.4',ms=3,mfc='white')
Iv=[20,50,100,200,300,400,450]; Vv=[1.55,1.62,1.68,1.78,1.86,1.93,1.97]; ax.plot(Iv,Vv,'s',color='0.4',ms=2.5,mfc='white')
ax2.axhline(50,color='0.6',lw=0.6,ls='-.'); ax2.text(230,51.5,'50 mW max',fontsize=7)
for x in (161.6,400): ax.axvline(x,color='0.6',lw=0.6,ls=':')
ax.text(164,0.15,'$I_{th}$',fontsize=8); ax.text(372,0.15,'$I_{max}$',fontsize=8)
ax.plot([],[],'k--',label='Optical power (model)'); ax.plot([],[],'o',color='0.4',ms=3,mfc='white',label='Datasheet LIV curve'); ax.legend(loc='upper left',fontsize=7,frameon=False)
for a in (ax,ax2): a.tick_params(direction='in',width=0.6)
ax.grid(lw=0.3,color='0.85'); fig.tight_layout(pad=0.3); fig.savefig('fig_dpss_iv_pi.png',dpi=300)
fig,ax=plt.subplots(figsize=(3.5,2.4)); sty={'10u':('k-','τ = 10 µs'),'100u':('k--','τ = 100 µs'),'1m':('k:','τ = 1 ms')}
rows=[]
for t,(s,l) in sty.items():
    a=np.loadtxt(f'tr_tau{t}.txt'); tt=(a[:,0]-1e-3)*1e3; p=a[:,1]*1e3; ax.plot(tt,p,s,lw=1,label=l)
    tu=np.linspace(0,0.0115,230001); pu=np.interp(tu,a[:,0]-1e-3,a[:,1])
    for T in [100e-6,1e-3,10e-3]:
        m=tu<=T; E=np.trapezoid(pu[m],tu[m]); rows.append((t,T,E/(pu[np.argmin(abs(tu-9.9e-3))]*T)))
ax.plot([-0.5,0,0,10,10,11.5],[0,0,40,40,0,0],color='0.7',lw=0.8,label='Pump current (scaled)')
ax.set_xlabel('Time from current step (ms)'); ax.set_ylabel('532 nm output (mW)'); ax.set_xlim(-0.5,11.5); ax.set_ylim(-2,48)
ax.legend(loc='center right',fontsize=7,frameon=False); ax.grid(lw=0.3,color='0.85'); ax.tick_params(direction='in',width=0.6)
fig.tight_layout(pad=0.3); fig.savefig('fig_dpss_tau.png',dpi=300)
print('tau, exposure, delivered fraction (laser switched on at exposure start)')
for r in rows: print(f'{r[0]:>5} {r[1]*1e6:7.0f} us  {r[2]*100:6.1f} %')
