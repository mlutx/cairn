const handleSignUp = async () => {
  try {
    const result = await signUp(email, password);
    
    if (result.message?.includes('verify your account')) {
      setStatus('verification-needed');
      setMessage(`We've sent a verification link to ${email}.`);
    } else {
      // Handle successful immediate signup
      setSession({
        user_id: result.user_id,
        access_token: result.access_token!,
        refresh_token: result.refresh_token!
      });
      setStatus('success');
      setMessage('Successfully signed up!');
    }
  } catch (error) {
    console.error('Signup error:', error);
    setStatus('error');
    setMessage(error instanceof Error ? error.message : 'Failed to sign up');
  }
};

const handleSignOut = async () => {
  try {
    await signOut();
    setSession(null); // Clear session state
    setStatus('signed-out');
    setMessage('Successfully signed out');
  } catch (error) {
    console.error('Signout error:', error);
    setStatus('error');
    setMessage('Failed to sign out');
  }
}; 