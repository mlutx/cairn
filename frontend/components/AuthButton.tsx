interface ImportMetaEnv {
  VITE_API_URL: string;
}  
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';


const handleAuth = async () => {
  try {
    if (!session) {
      // Login flow
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          password: password
        }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();
      // Handle successful login (store token, update state, etc.)
      
    } else {
      // Signup flow
      const response = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          password: password
        }),
      });

      if (!response.ok) {
        throw new Error('Signup failed');
      }

      const data = await response.json();
      // Handle successful signup
    }
  } catch (error) {
    console.error('Authentication error:', error);
    // Handle error state
  }
}; 