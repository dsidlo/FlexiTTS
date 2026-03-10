/**
 * Debug Logger for FlexiTTS
 * Logs to /tmp/FlexiTTS.log with unique identifiers
 */

const LOG_FILE = '/tmp/FlexiTTS.log';

// Enable debug logging via localStorage or environment
const isDebugEnabled = (): boolean => {
  try {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('FlexiTTS_DEBUG') === '1' || 
             process.env.VITE_DEBUG === '1';
    }
  } catch (e) {
    // localStorage not available
  }
  return false;
};

/**
 * Generate unique identifier for log location
 * Format: [Filename:Function:Line] or [Component:Function]
 */
const generateId = (component: string, functionName: string, line?: string): string => {
  return line ? `[${component}:${functionName}:${line}]` : `[${component}:${functionName}]`;
};

/**
 * Write log to file via Electron IPC if available, otherwise console
 * All UI logs are prefixed with [UI] for easy identification
 */
const writeLog = async (level: string, id: string, message: string, data?: unknown): Promise<void> => {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] [UI] ${level} ${id} ${message}`;
  
  // Log to console first
  if (level === 'ERROR') {
    console.error(logLine, data || '');
  } else if (level === 'WARN') {
    console.warn(logLine, data || '');
  } else {
    console.log(logLine, data || '');
  }
  
  // Try to write to file via Electron
  try {
    if (typeof window !== 'undefined' && (window as unknown as { api?: { writeFile?: (path: string, content: string) => Promise<void> } }).api?.writeFile) {
      const dataStr = data ? ` | DATA: ${JSON.stringify(data, null, 2)}` : '';
      const fullLine = `${logLine}${dataStr}\n`;
      await (window as unknown as { api: { writeFile: (path: string, content: string) => Promise<void> } }).api.writeFile(LOG_FILE, fullLine);
    }
  } catch (e) {
    // Silent fail - console logging already done
  }
};

/**
 * Debug logger object with methods for different log levels
 */
export const debugLog = {
  /**
   * Log debug message
   * @param id - Unique identifier [Component:Function:Line]
   * @param message - Log message
   * @param data - Optional data to log
   */
  debug: (id: string, message: string, data?: unknown): void => {
    if (isDebugEnabled()) {
      void writeLog('DEBUG', id, message, data);
    }
  },

  /**
   * Log info message (always logged)
   * @param id - Unique identifier [Component:Function:Line]
   * @param message - Log message
   * @param data - Optional data to log
   */
  info: (id: string, message: string, data?: unknown): void => {
    void writeLog('INFO', id, message, data);
  },

  /**
   * Log warning message
   * @param id - Unique identifier [Component:Function:Line]
   * @param message - Log message
   * @param data - Optional data to log
   */
  warn: (id: string, message: string, data?: unknown): void => {
    void writeLog('WARN', id, message, data);
  },

  /**
   * Log error message
   * @param id - Unique identifier [Component:Function:Line]
   * @param message - Log message
   * @param error - Error object or data
   */
  error: (id: string, message: string, error?: unknown): void => {
    const errorData = error instanceof Error 
      ? { message: error.message, stack: error.stack, name: error.name }
      : error;
    void writeLog('ERROR', id, message, errorData);
  },

  /**
   * Log exception with full details
   * @param id - Unique identifier [Component:Function:Line]
   * @param context - Context where exception occurred
   * @param error - The caught error
   * @param extraData - Additional context data
   */
  exception: (id: string, context: string, error: unknown, extraData?: Record<string, unknown>): void => {
    const errorInfo = error instanceof Error 
      ? { 
          message: error.message, 
          stack: error.stack, 
          name: error.name,
          ...(extraData || {})
        }
      : { 
          error: String(error),
          ...(extraData || {})
        };
    
    void writeLog('EXCEPTION', id, `EXCEPTION in ${context}: ${'message' in errorInfo ? errorInfo.message : String(error)}`, errorInfo);
  },

  /**
   * Generate ID helper for consistent formatting
   */
  id: generateId
};

/**
 * Higher-order function to wrap async functions with logging
 */
export const withLogging = <T extends (...args: unknown[]) => Promise<unknown>>(
  component: string,
  functionName: string,
  fn: T
): ((...args: Parameters<T>) => Promise<ReturnType<T>>) => {
  return async (...args: Parameters<T>): Promise<ReturnType<T>> => {
    const id = generateId(component, functionName);
    debugLog.info(id, `ENTER ${functionName}`, { args: args.length });
    
    try {
      const result = await fn(...args);
      debugLog.info(id, `EXIT ${functionName} - SUCCESS`);
      return result as ReturnType<T>;
    } catch (error) {
      debugLog.exception(id, functionName, error, { args: args.length });
      throw error;
    }
  };
};

export default debugLog;
