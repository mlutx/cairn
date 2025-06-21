import { createContext, useContext, ReactNode, useState, useEffect } from "react";

interface User {
  id: string;
  email: string;
  team_id: string;
  first_name: string;
  last_name: string;
}

interface AuthContextType {
  user: User;
  setUser: (user: User) => void;
  refreshUser: () => Promise<void>;
}

// Default user that will always be available
const defaultUser: User = {
  id: "local-user-id",
  email: "local@example.com",
  team_id: "local-team-id",
  first_name: "Local",
  last_name: "User"
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(defaultUser);

  // This function now just ensures the default user is set
  const refreshUser = async () => {
    setUser(defaultUser);
  };

  useEffect(() => {
    refreshUser();
  }, []);

  return (
    <AuthContext.Provider value={{ user, setUser, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
