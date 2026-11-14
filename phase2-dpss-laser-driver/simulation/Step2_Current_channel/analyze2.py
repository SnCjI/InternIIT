import numpy as np
col=lambda a,k: a[:,2*k+1]
a=np.loadtxt('t1_nom.txt'); x=a[:,0]; I=abs(col(a,0))
print('DC: '+' '.join('%.2fV->%.1fmA'%(v,I[np.argmin(abs(x-v))]*1e3) for v in [0,1,2,2.244,2.5,3,3.3]))
lin=(x>0.2)&(x<2.4); p=np.polyfit(x[lin],I[lin],1); print(' slope %.3f mA/V offset %.3f mA, max nonlin %.4f mA'%(p[0]*1e3,p[1]*1e3,abs(I[lin]-np.polyval(p,x[lin])).max()*1e3))
for f in ['t1_low','t1_high']:
    b=np.loadtxt(f+'.txt'); print(' rail %s: I(2.244V)=%.2f mA, I(3.3V)=%.2f mA'%(f,abs(col(b,0))[np.argmin(abs(b[:,0]-2.244))]*1e3,abs(col(b,0))[-1]*1e3))
a=np.loadtxt('t2_gate.txt'); t=a[:,0]; I=col(a,0); P=col(a,2)
Ion=np.median(I[(t>560e-6)&(t<595e-6)]); pk=I[(t>500e-6)&(t<650e-6)].max()
print('GATE: Ion=%.2f mA (P=%.1f mW) overshoot=%.3f%%'%(Ion*1e3,np.median(P[(t>560e-6)&(t<595e-6)])*1e3,(pk/Ion-1)*100))
def tc(fr,up,t0):
    k=np.argmax((t>t0)&((I>=fr*Ion) if up else (I<=fr*Ion))); return (t[k]-t0)*1e6
print(' rise t10/t50/t90 = %.2f/%.2f/%.2f us'%(tc(.1,1,500e-6),tc(.5,1,500e-6),tc(.9,1,500e-6)))
print(' fall t90/t50/t10 = %.2f/%.2f/%.2f us'%(tc(.9,0,600e-6),tc(.5,0,600e-6),tc(.1,0,600e-6)))
print(' off current %.4f mA'%(np.median(I[(t>700e-6)&(t<890e-6)])*1e3))
m=(t>=500e-6)&(t<=600e-6); print(' charge in 100us window %.1f%% ; pulse-width error (charge) %.2f us'%(np.trapezoid(I[(t>=500e-6)&(t<700e-6)],t[(t>=500e-6)&(t<700e-6)])/(Ion*100e-6)*100, (np.trapezoid(I[(t>=500e-6)&(t<700e-6)],t[(t>=500e-6)&(t<700e-6)])/Ion-100e-6)*1e6))
b=np.loadtxt('t3_power.txt'); t=b[:,0]; I=col(b,0); Is=abs(col(b,1)); vc=col(b,5)
print('POWER-UP 0-10 ms: max laser I=%.4f mA, max sink I=%.4f mA'%(abs(I[t<10e-3]).max()*1e3,Is[t<10e-3].max()*1e3))
print(' ramp: 60ms %.1f, 110ms %.1f, max %.2f mA'%(np.interp(60e-3,t,I)*1e3,np.interp(110e-3,t,I)*1e3,I[(t>10e-3)&(t<150e-3)].max()*1e3))
print(' power-down: max I %.2f mA; max reverse V %.3f V'%(I[t>150e-3].max()*1e3,vc[t>149e-3].max()))
c=np.loadtxt('t4_with.txt'); t=c[:,0]; print('REVERSE kick: max V(cath-anode)=%.3f V; laser I before/after %.1f/%.1f mA'%(col(c,1).max(),np.interp(190e-6,t,col(c,0))*1e3,np.interp(290e-6,t,col(c,0))*1e3))
d=np.loadtxt('t5_comp.txt'); x=d[:,0]; I=abs(col(d,0))
for v in [2.244,2.5,2.6]:
    k=np.argmin(abs(x-v)); print('COMPLIANCE DAC %.3f: I=%.2f mA  Vlaser=%.3f V  Vds=%.3f V  Pmos=%.3f W'%(v,I[k]*1e3,-col(d,3)[k],col(d,1)[k]-col(d,2)[k],I[k]*(col(d,1)[k]-col(d,2)[k])))
