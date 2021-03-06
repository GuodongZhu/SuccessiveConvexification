from sympy import symbols, Matrix, Function
from time import time
import numpy as np
import sympy

class Dynamics(object):

    ''' The Dynamics class defines all dynamic functions symbolically.

        It can be evaluted if "constants" is not None,
            otherwise will generate a .py file with all the definitions
    '''

    def __init__(self, constants = None):

        start = time()


        # --------------------------------------------------------- setup

        # Variable Symbols
        m = symbols('m')
        r = Matrix(symbols('r0 r1 r2'))     # aka rI
        v = Matrix(symbols('v0 v1 v2'))     # aka vI
        q = Matrix(symbols('q0 q1 q2 q3'))  # aka qBI
        w = Matrix(symbols('w0 w1 w2'))     # aka wB

        self.x = [
                    [m],
                    [r[0]], [r[1]], [r[2]],
                    [v[0]], [v[1]], [v[2]],
                    [q[0]], [q[1]], [q[2]], [q[3]],
                    [w[0]], [w[1]], [w[2]]
                ]

        self.u = Matrix(symbols('u0 u1 u2', positive=True))
        self.s = symbols('s', positive=True)  # dtime/dtau

        # Constants
        if constants is not None:

            generate_code = False

            alpha = constants['alpha']
            rTB = Matrix(constants['rTB'])
            J = Matrix(constants['J'])
            g = Matrix(constants['g'])

        else:

            alpha = symbols('alpha')
            rTB = Matrix(symbols('rTB0 rTB1 rTB2'))
            g = Matrix(symbols('gx gy gz'))

            J = sympy.zeros(3,3)
            J[0,0] = symbols('J00')
            J[1,1] = symbols('J11')
            J[2,2] = symbols('J22')

            generate_code = True

        # --------------------------------------------------------- dx / dt
        # f(x) = first derivative of x with respect to t
        self.f = sympy.zeros(14,1)

        u_mag = sympy.sqrt(self.u[0]**2. + self.u[1]**2. + self.u[2]**2.)

        self.f[0]       = (-alpha) * u_mag  # dm / dt = -alpha * ||u||
        self.f[1:4,:]   = (v) # dr/dt = velocity

        # dv/dt = gravity + (pointed thrust)/mass
        self.f[4:7,:]   = (1./m) * self.cIB(q) * self.u + g
        self.f[7:11,:]  = (1./2.) * self.Om(w) * q

        # J.T == J.inv() due to orthogonality
        self.f[11:14,:] = J.pinv_solve(rTB.cross(self.u) - w.cross(J*w))

        self.A = self.s * self.f.jacobian(self.x)  # df/dx = (17b)
        self.B = self.s * self.f.jacobian(self.u)  # df/du = (17c)

        print(' >> Dynamics class init took',time() - start,'sec')

        # --------------------------------------------------------- code gen

        if generate_code:
            self.generate_functions()

    @staticmethod
    def Om(w, numpy=False):
        w0, w1, w2 = w

        if numpy:
            Omega = np.zeros((4,4))
        else:
            Omega = sympy.zeros(4,4)

        Omega[0,0] = 0
        Omega[0,1] = -w0
        Omega[0,2] = -w1
        Omega[0,3] = -w2
        Omega[1,0] = +w0
        Omega[1,1] = 0
        Omega[1,2] = +w2
        Omega[1,3] = -w1
        Omega[2,0] = +w1
        Omega[2,1] = -w2
        Omega[2,2] = 0
        Omega[2,3] = +w0
        Omega[3,0] = +w2
        Omega[3,1] = +w1
        Omega[3,2] = -w0
        Omega[3,3] = 0

        return Omega

    @staticmethod
    def cIB(q, numpy=False):
        q0, q1, q2, q3 = q

        if numpy:
            cIB_m = np.zeros((3,3))
        else:
            cIB_m = sympy.zeros(3,3)

        cIB_m[0,0] = 1-2*(q2**2 + q3**2)
        cIB_m[0,1] = 2*(q1*q2 + q0*q3)
        cIB_m[0,2] = 2*(q1*q3 - q0*q2)

        cIB_m[1,0] = 2*(q1*q2 - q0*q3)
        cIB_m[1,1] = 1-2*(q1**2 + q3**2)
        cIB_m[1,2] = 2*(q2*q3 + q0*q1)

        cIB_m[2,0] = 2*(q1*q3 + q0*q2)
        cIB_m[2,1] = 2*(q2*q3 - q0*q1)
        cIB_m[2,2] = 1-2*(q1**2 + q2**2)

        return cIB_m

    def get(self, name, xi, ui, si):

        substitutions = []
        for n, sym in enumerate(self.x):
            substitutions.append( (sym[0], xi[n,0]) )

        for n, sym in enumerate(self.u):
            substitutions.append( (sym, ui[n]) )

        substitutions.append((self.s, si))

        function = getattr(self, name)
        matrix = function.subs(substitutions)

        return np.array(matrix).astype(np.float64)

    def generate_functions(self):
        ''' Code generation of the symbolic dynamic functions '''

        tab = '    '  # 4 spaces
        functions = {'A':self.A, 'B':self.B, 'f':self.f}

        with open('dynamics_functions.py','w') as f:

            f.write('""" This was generated by dynamics_generation.py """' + '\n\n')
            f.write('from numpy import sqrt' + '\n')
            f.write('import numpy as np' + '\n\n')

            f.write('class Dynamics:' + '\n\n')

            set_parameters_string = tab

            set_parameters_string += 'def set_parameters(self, parms):' + '\n'
            set_parameters_string += tab
            set_parameters_string += tab

            set_parameters_string += 'for name, val in parms.items():' + '\n'
            set_parameters_string += tab
            set_parameters_string += tab
            set_parameters_string += tab
            set_parameters_string += 'setattr(self, name, val)'

            f.write(set_parameters_string + '\n')

            for name, matrix in functions.items():

                if name != 'f':
                    f.write('\n')
                    f.write(tab)
                    f.write('def ' + name + '(self, x, u, s):' + '\n')

                else:
                    f.write('\n')
                    f.write(tab)
                    f.write('def ' + name + '(self, x, u):' + '\n')

                variables_unpacking = [
                    'm, r0, r1, r2, v0, v1, v2, q0, q1, q2, q3, w0, w1, w2 = x',
                    'u0, u1, u2 = u',
                ]

                constants_unpacking = [
                                    "J = self.J",
                                    "alpha = self.alpha",
                                    "gx, gy, gz = self.g_I",
                                    "rTB0, rTB1, rTB2 = self.rTB",
                ]

                for v in variables_unpacking:
                    f.write(tab + tab + v + '\n')

                f.write('\n')

                for c in constants_unpacking:
                    f.write(tab + tab + c + '\n')

                f.write('\n' + tab)


                if name != 'f':
                    f.write(tab + name + 'm')
                    f.write(' = np.zeros(' + str(matrix.shape) + ')\n')

                else:
                    f.write(tab + name + 'm')
                    f.write(' = np.zeros((' + str(matrix.shape[0]) + ',))\n')

                for n in range(matrix.shape[0]):
                    for m in range(matrix.shape[1]):

                        value = str(matrix[n,m])

                        if value != '0':

                            genline  = tab
                            genline += name + 'm'

                            if name != 'f':
                                genline += '[' + str(n) + ', ' + str(m) +']='
                                genline += str(value)
                            else:
                                genline += '[' + str(n) + ']='
                                genline += str(value)

                            # J matrix should be indexed instead of unpacked
                            for i in range(3):
                                for j in range(3):
                                    genline = genline.replace(
                                                'J'+str(i)+str(j),
                                                'J['+str(i)+','+str(j)+']',
                                                    )

                            f.write(tab + genline + '\n')

                f.write(tab + tab + 'return ' + name + 'm' + '\n')

            print('Done writing to file')

def runtime_tests():
    d = Dynamics(constants)
    start = time()
    A = d.get('A', x, u, s)
    B = d.get('B', x, u, s)
    f = d.get('f', x, u, s)
    print('took',time()-start,'sec to run A, B and f')

    print('A',A.shape, A)
    print('B',B.shape, B)
    print('f',f.shape, f)

    print('Ax', A*x)
    print('Bu', B*u)

def function_tests():

    import dynamics_functions as funk

    f = funk.Dynamics()
    f.set_parameters(constants)

    # If these can be assigned, all is well in set_parameters
    a = (f.alpha),(f.rTB),(f.g_I),(f.J)

    # If this executes, all is well in the dynamics functions
    x = np.random.random((14,1))
    u = np.random.random((3,1))
    s = 1

    f.A(x,u,s)
    f.B(x,u,s)
    f.f(x,u)

    print('Tests passed')

if __name__ == '__main__':

    import numpy as np

    constants = {}
    constants['alpha'] = 0.1
    constants['rTB'] = -1e-2 * np.array([1,0,0])
    constants['J'] = 1e-2 * np.eye(3)
    constants['g_I'] = np.array([ -1, 0, 0])  # inertial frame

    d = Dynamics()

    function_tests()
