import numpy as np,matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Liberation Serif','font.size':9,'axes.linewidth':0.7,'mathtext.fontset':'stix'})
col=lambda a,k: a[:,2*k+1]
def fin(ax): ax.grid(lw=0.3,color='0.85'); ax.tick_params(direction='in',width=0.6)
# DC
a=np.loadtxt('t1_nom.txt'); x=a[:,0]; I=abs(col(a,0))*1e3; P=col(a,1)*1e3
fig,ax=plt.subplots(figsize=(3.5,2.4)); ax.plot(x,I,'k-',lw=1,label='Laser current'); ax.axhline(400,color='0.5',ls=':',lw=0.8); ax.text(0.05,408,'400 mA hardware clamp',fontsize=7)
ax.axvline(2.5,color='0.7',lw=0.6,ls='--'); ax.text(2.53,60,'DAC full scale\n(2.5 V)',fontsize=7)
ax.set_xlabel('DAC output (V)'); ax.set_ylabel('Laser current (mA)'); ax.set_ylim(0,460); ax.set_xlim(0,3.3)
ax2=ax.twinx(); ax2.plot(x,P,'k--',lw=1); ax2.set_ylabel('532 nm output (mW)'); ax2.set_ylim(0,69); ax2.tick_params(direction='in',width=0.6)
ax.plot([],[],'k--',label='Optical power'); ax.legend(loc='upper left',bbox_to_anchor=(0,0.85),fontsize=7,frameon=False); fin(ax)
fig.tight_layout(pad=0.3); fig.savefig('fig_s2_dc.png',dpi=300)
# gating
a=np.loadtxt('t2_gate.txt'); t=a[:,0]*1e6; I=col(a,0)*1e3; P=col(a,2)*1e3; g=col(a,3)
fig,axs=plt.subplots(2,1,figsize=(3.5,3.2),sharex=True,gridspec_kw={'height_ratios':[1,2]})
axs[0].plot(t,g,'k-',lw=0.9); axs[0].set_ylabel('GATE (V)'); axs[0].set_ylim(-0.4,4)
axs[1].plot(t,I,'k-',lw=1,label='Laser current (mA)'); axs[1].plot(t,P*5,'k--',lw=1,label='Optical power ×5 (mW)')
axs[1].set_ylabel('mA  /  mW×5'); axs[1].set_xlabel('Time (µs)'); axs[1].set_xlim(470,640); axs[1].set_ylim(-15,470); axs[1].legend(fontsize=7,frameon=False,loc='upper right',bbox_to_anchor=(1,1.0))
for q in axs: fin(q)
fig.tight_layout(pad=0.3); fig.savefig('fig_s2_gate.png',dpi=300)
# power
b=np.loadtxt('t3_power.txt'); t=b[:,0]*1e3; I=col(b,0)*1e3; en=col(b,3); dac=col(b,4)
fig,axs=plt.subplots(2,1,figsize=(3.5,3.2),sharex=True)
axs[0].plot(t,dac,'k-',lw=0.9,label='DAC'); axs[0].plot(t,en,'k--',lw=0.9,label='ENABLE'); axs[0].set_ylabel('Voltage (V)'); axs[0].set_ylim(-0.3,4.2); axs[0].legend(fontsize=7,frameon=False,ncol=2,loc='upper right')
axs[0].axvspan(0,2,color='0.9'); axs[0].text(2.5,3.6,'rails ramp',fontsize=7)
axs[1].plot(t,I,'k-',lw=1); axs[1].set_ylabel('Laser current (mA)'); axs[1].set_xlabel('Time (ms)'); axs[1].set_ylim(-15,420)
axs[1].axvspan(150,151,color='0.85'); axs[1].text(118,380,'power-down',fontsize=7)
for q in axs: fin(q); q.set_xlim(0,160)
fig.tight_layout(pad=0.3); fig.savefig('fig_s2_power.png',dpi=300)
